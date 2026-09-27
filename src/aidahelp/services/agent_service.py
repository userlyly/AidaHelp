"""把 HTTP 会话、MySQL 原始消息、Memory 和 LangGraph 串成一个完整回合。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.agent.nodes import AgentNodes
from aidahelp.agent.workflow import build_workflow
from aidahelp.config import Settings
from aidahelp.domain.enums import MessageRole, MessageType
from aidahelp.domain.exceptions import (
    ConversationNotFoundError,
    ModelUnavailableError,
    PendingActionNotFoundError,
)
from aidahelp.integrations.llm.base import ChatModel, TokenUsage
from aidahelp.integrations.llm.errors import ChatModelUpstreamError
from aidahelp.memory import MemoryService
from aidahelp.persistence.repositories.conversation_repository import ConversationRepository
from aidahelp.security.audit import record_security_event
from aidahelp.security.guardrails import SecurityGuard
from aidahelp.services.conversation_service import ConversationService
from aidahelp.services.retrieval_service import RetrievalService
from aidahelp.tools import ToolExecutor, ToolRegistry


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    conversation_id: str
    assistant_message_id: str
    answer: str
    model: str
    created_at: datetime
    user_message_id: str | None = None
    intent: str | None = None
    route: str | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)


class AgentService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        model: ChatModel,
        retrieval: RetrievalService,
        registry: ToolRegistry,
        checkpointer: Any,
        settings: Settings,
    ) -> None:
        self.session = session
        self.model = model
        self.retrieval = retrieval
        self.registry = registry
        self.checkpointer = checkpointer
        self.settings = settings
        self.security = SecurityGuard(settings.guardrails_enabled)
        self.conversation_service = ConversationService(session)
        self.conversations = ConversationRepository(session)

    async def chat(
        self,
        *,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        title: str | None = None,
    ) -> AgentTurnResult:
        decision = self.security.inspect_input(message)
        if not decision.allowed:
            await record_security_event(
                self.session,
                event_type="prompt_injection_blocked",
                severity="high",
                user_id=user_id,
                reason=decision.reason or "unsafe input",
                details={"rule": decision.rule, "content_length": len(message)},
            )
            self.security.require_safe_input(message)
        if conversation_id is None:
            conversation = await self.conversation_service.create_conversation(
                user_id=user_id,
                title=title or self._default_title(message),
            )
        else:
            async with self.session.begin():
                conversation = await self.conversations.get_for_user(
                    conversation_id=conversation_id,
                    user_id=user_id,
                )
                if conversation is None:
                    raise ConversationNotFoundError()

        user_message = await self.conversation_service.append_message(
            conversation_id=conversation.id,
            user_id=user_id,
            role=MessageRole.USER,
            content=message,
            metadata={"source": "agent_api"},
        )
        memory = await MemoryService(self.session, self.settings).build_context(
            conversation_id=conversation.id,
            user_id=user_id,
        )
        initial_state = {
            "user_id": user_id,
            "conversation_id": conversation.id,
            "question": message,
            # Checkpointer 会保留同一 thread 的旧状态；本轮输出通道必须显式清空。
            "resolved_query": "",
            "intent": "",
            "intent_confidence": 0.0,
            "route": "",
            "summary": memory.summary,
            "facts": memory.facts,
            "context_messages": [
                {
                    "role": item.role,
                    "content": item.content,
                    "name": item.name,
                    "tool_call_id": item.tool_call_id,
                }
                for item in memory.messages
            ],
            "agent_messages": [],
            "evidence": [],
            "low_confidence": False,
            "final_answer": "",
            "citations": [],
            "pending_tool_calls": [],
            "steps": 0,
            "usage": {},
            "trace": {"prompt_cache_key": memory.prompt_cache_key},
        }
        result = await self._invoke(initial_state, conversation.id)
        return await self._persist_result(
            result=result,
            user_id=user_id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
        )

    async def resume(
        self,
        *,
        user_id: str,
        conversation_id: str,
        confirmed: bool,
    ) -> AgentTurnResult:
        async with self.session.begin():
            conversation = await self.conversations.get_for_user(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            if conversation is None:
                raise ConversationNotFoundError()
        result = await self._invoke(Command(resume={"confirmed": confirmed}), conversation_id)
        if not result or (not result.get("final_answer") and not result.get("__interrupt__")):
            raise PendingActionNotFoundError()
        return await self._persist_result(
            result=result,
            user_id=user_id,
            conversation_id=conversation_id,
            user_message_id=None,
        )

    async def _invoke(self, graph_input: Any, conversation_id: str) -> dict:
        nodes = AgentNodes(
            model=self.model,
            retrieval=self.retrieval,
            registry=self.registry,
            executor=ToolExecutor(self.session, self.settings),
            settings=self.settings,
        )
        graph = build_workflow(nodes, checkpointer=self.checkpointer)
        config = {
            "configurable": {"thread_id": conversation_id},
            "recursion_limit": self.settings.agent_max_steps * 3 + 10,
        }
        try:
            return await graph.ainvoke(graph_input, config=config)
        except ChatModelUpstreamError as exc:
            raise ModelUnavailableError() from exc

    async def _persist_result(
        self,
        *,
        result: dict,
        user_id: str,
        conversation_id: str,
        user_message_id: str | None,
    ) -> AgentTurnResult:
        pending = self._pending_action(result)
        answer = result.get("final_answer") or (
            "请确认是否继续执行上述操作。"
            if pending
            else "本轮达到最大工具步数，请缩小问题范围后重试。"
        )
        answer = self.security.sanitize_output(answer)
        usage_data = result.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens"),
            completion_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens"),
        )
        assistant_message = await self.conversation_service.append_message(
            conversation_id=conversation_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=answer,
            message_type=MessageType.EVENT if pending else MessageType.TEXT,
            metadata={
                "source": "langgraph",
                "model": self.model.name,
                "intent": result.get("intent"),
                "route": result.get("route"),
                "citations": result.get("citations") or [],
                "pending_action": pending,
                "trace": result.get("trace") or {},
                "usage": usage_data,
            },
        )
        return AgentTurnResult(
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message.id,
            answer=answer,
            model=self.model.name,
            usage=usage,
            created_at=assistant_message.created_at,
            intent=result.get("intent"),
            route=result.get("route"),
            citations=list(result.get("citations") or []),
            pending_action=pending,
        )

    @staticmethod
    def _pending_action(result: dict) -> dict[str, Any] | None:
        interrupts = result.get("__interrupt__") or []
        if not interrupts:
            return None
        value = getattr(interrupts[0], "value", None)
        return dict(value) if isinstance(value, dict) else {"value": value}

    @staticmethod
    def _default_title(message: str) -> str:
        return " ".join(message.split())[:30] or "新客服会话"
