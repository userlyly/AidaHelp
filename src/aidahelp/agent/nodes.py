"""阶段 6～9 工作流节点实现。"""

import re
from dataclasses import asdict
from typing import Any

from langgraph.types import interrupt

from aidahelp.agent.coreference import resolve_reference
from aidahelp.agent.intent import classify_intent
from aidahelp.agent.prompts import KNOWLEDGE_PROMPT, SYSTEM_PROMPT
from aidahelp.agent.routing import route_by_intent
from aidahelp.agent.state import AgentState
from aidahelp.config import Settings
from aidahelp.domain.enums import ToolPermission
from aidahelp.integrations.llm.base import ChatMessage, ChatModel, ToolCall
from aidahelp.security.guardrails import SecurityGuard
from aidahelp.services.retrieval_service import RetrievalService
from aidahelp.tools.executor import ToolExecutor
from aidahelp.tools.registry import ToolRegistry

_ORDER_ID = re.compile(r"\b(?:ORD|ORDER|AIDA)[-_]?\d{4,}\b", re.IGNORECASE)


def _to_message(item: dict[str, Any]) -> ChatMessage:
    return ChatMessage(
        role=str(item["role"]),
        content=str(item.get("content") or ""),
        name=item.get("name"),
        tool_call_id=item.get("tool_call_id"),
        tool_calls=[ToolCall(**call) for call in item.get("tool_calls", [])],
    )


def _message_dict(message: ChatMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "name": message.name,
        "tool_call_id": message.tool_call_id,
        "tool_calls": [asdict(call) for call in message.tool_calls],
    }


class AgentNodes:
    def __init__(
        self,
        *,
        model: ChatModel,
        retrieval: RetrievalService,
        registry: ToolRegistry,
        executor: ToolExecutor,
        settings: Settings,
    ) -> None:
        self.model = model
        self.retrieval = retrieval
        self.registry = registry
        self.executor = executor
        self.settings = settings
        self.security = SecurityGuard(settings.guardrails_enabled)

    async def understand(self, state: AgentState) -> dict:
        history = [_to_message(item) for item in state.get("context_messages", [])]
        resolved = resolve_reference(state["question"], history[:-1])
        intent = classify_intent(resolved)
        route = route_by_intent({"intent": intent.intent.value})
        return {
            "resolved_query": resolved,
            "intent": intent.intent.value,
            "intent_confidence": intent.confidence,
            "route": route,
            "trace": {
                **state.get("trace", {}),
                "matched_keywords": list(intent.matched_keywords),
                "understand": "done",
            },
        }

    async def retrieve(self, state: AgentState) -> dict:
        result = await self.retrieval.search(state["resolved_query"], top_k=5)
        evidence = [asdict(item) for item in result.evidence]
        citations = [
            {
                "index": index,
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "section_path": item.section_path,
                "score": item.rerank_score or item.recall_score,
            }
            for index, item in enumerate(result.evidence, start=1)
        ]
        return {
            "evidence": evidence,
            "citations": citations,
            "low_confidence": result.low_confidence,
            "trace": {**state.get("trace", {}), "retrieve": "done"},
        }

    async def answer(self, state: AgentState) -> dict:
        if state.get("low_confidence"):
            return {
                "final_answer": "现有企业知识不足以可靠回答这个问题，我建议转人工进一步确认。",
                "trace": {**state.get("trace", {}), "answer": "low_confidence_refusal"},
            }
        messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
        if state.get("summary"):
            messages.append(
                ChatMessage(role="system", content=f"较早对话摘要：\n{state['summary']}")
            )
        messages.extend(_to_message(item) for item in state.get("context_messages", []))
        if state.get("evidence"):
            evidence_text = "\n\n".join(
                f"[{index}] {item['section_path']}\n"
                f"{self.security.sanitize_untrusted(item['content'])}"
                for index, item in enumerate(state["evidence"], start=1)
            )
            messages.insert(
                1,
                ChatMessage(
                    role="system",
                    content=KNOWLEDGE_PROMPT.format(evidence=evidence_text),
                ),
            )
        response = await self.model.generate(messages)
        return {
            "final_answer": response.content,
            "usage": asdict(response.usage),
            "trace": {**state.get("trace", {}), "answer": "model"},
        }

    async def agent(self, state: AgentState) -> dict:
        specs = [
            item
            for item in await self.registry.all_specs()
            if item.permission == ToolPermission.READ
        ]
        if state.get("agent_messages"):
            working = [_to_message(item) for item in state["agent_messages"]]
        else:
            working = [ChatMessage(role="system", content=SYSTEM_PROMPT)]
            if state.get("summary"):
                working.append(
                    ChatMessage(role="system", content=f"较早对话摘要：\n{state['summary']}")
                )
            working.extend(_to_message(item) for item in state.get("context_messages", []))
        response = await self.model.generate(
            working,
            tools=[item.model_schema() for item in specs],
        )
        assistant = ChatMessage(
            role="assistant",
            content=response.content,
            tool_calls=response.tool_calls,
        )
        working.append(assistant)
        return {
            "agent_messages": [_message_dict(item) for item in working],
            "pending_tool_calls": [asdict(item) for item in response.tool_calls],
            "final_answer": response.content if not response.tool_calls else "",
            "usage": asdict(response.usage),
            "trace": {**state.get("trace", {}), "agent_model_calls": state.get("steps", 0) + 1},
        }

    async def tools(self, state: AgentState) -> dict:
        specs = {item.name: item for item in await self.registry.all_specs()}
        working = [_to_message(item) for item in state.get("agent_messages", [])]
        for call in state.get("pending_tool_calls", []):
            result = await self.executor.execute(
                spec=specs.get(str(call["name"])),
                tool_call_id=str(call["id"]),
                name=str(call["name"]),
                arguments=dict(call.get("arguments") or {}),
                user_id=state["user_id"],
                conversation_id=state["conversation_id"],
            )
            working.append(
                ChatMessage(
                    role="tool",
                    content=self.security.sanitize_untrusted(result.content),
                    name=result.name,
                    tool_call_id=result.tool_call_id,
                )
            )
        return {
            "agent_messages": [_message_dict(item) for item in working],
            "pending_tool_calls": [],
            "steps": state.get("steps", 0) + 1,
            "trace": {**state.get("trace", {}), "tools": "executed"},
        }

    async def refund_flow(self, state: AgentState) -> dict:
        match = _ORDER_ID.search(state["resolved_query"])
        if match is None:
            return {"final_answer": "可以帮你申请退款。请先提供需要退款的订单号。"}
        order_id = match.group(0).upper()
        preview = {
            "type": "refund_confirmation",
            "title": "确认提交退款申请",
            "order_id": order_id,
            "reason": state["question"],
            "warning": "确认后会真实写入退款申请记录。",
        }
        decision = interrupt(preview)
        if not isinstance(decision, dict) or not decision.get("confirmed"):
            return {"final_answer": "已取消本次退款申请，没有产生业务写入。"}
        spec = await self.registry.by_name("submit_refund", include_mcp=False)
        result = await self.executor.execute(
            spec=spec,
            tool_call_id=f"refund-{state['conversation_id']}",
            name="submit_refund",
            arguments={
                "order_id": order_id,
                "reason": state["question"],
                "idempotency_key": f"refund:{state['conversation_id']}:{order_id}",
            },
            user_id=state["user_id"],
            conversation_id=state["conversation_id"],
            confirmed=True,
        )
        return {"final_answer": f"退款申请处理结果：{result.content}"}

    async def human_flow(self, state: AgentState) -> dict:
        category = "投诉" if state.get("intent") == "complaint" else "咨询"
        preview = {
            "type": "ticket_confirmation",
            "title": "确认创建人工客服工单",
            "category": category,
            "description": state["question"],
            "warning": "确认后会创建一条人工工单。",
        }
        decision = interrupt(preview)
        if not isinstance(decision, dict) or not decision.get("confirmed"):
            return {"final_answer": "已取消创建人工工单。"}
        spec = await self.registry.by_name("create_ticket", include_mcp=False)
        result = await self.executor.execute(
            spec=spec,
            tool_call_id=f"ticket-{state['conversation_id']}",
            name="create_ticket",
            arguments={"category": category, "description": state["question"]},
            user_id=state["user_id"],
            conversation_id=state["conversation_id"],
            confirmed=True,
        )
        return {"final_answer": f"人工工单处理结果：{result.content}"}
