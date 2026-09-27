"""LangGraph 节点之间传递的本轮状态。"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    user_id: str
    conversation_id: str
    question: str
    resolved_query: str
    intent: str
    intent_confidence: float
    route: str
    summary: str
    facts: dict[str, Any]
    context_messages: list[dict[str, Any]]
    agent_messages: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    low_confidence: bool
    final_answer: str
    citations: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    steps: int
    usage: dict[str, int | None]
    trace: dict[str, Any]
