"""意图到工作流出口的确定性映射。"""

from aidahelp.agent.intent import Intent
from aidahelp.agent.state import AgentState

_ROUTES = {
    Intent.KNOWLEDGE.value: "knowledge",
    Intent.REFUND.value: "refund",
    Intent.COMPLAINT.value: "human",
    Intent.HUMAN.value: "human",
    Intent.CHITCHAT.value: "direct",
    Intent.ORDER.value: "agent",
    Intent.LOGISTICS.value: "agent",
    Intent.AFTER_SALES.value: "agent",
    Intent.OTHER.value: "agent",
}


def route_by_intent(state: AgentState) -> str:
    return _ROUTES.get(state.get("intent", ""), "agent")


def continue_agent(state: AgentState, max_steps: int) -> str:
    if state.get("pending_tool_calls") and state.get("steps", 0) < max_steps:
        return "tools"
    return "done"
