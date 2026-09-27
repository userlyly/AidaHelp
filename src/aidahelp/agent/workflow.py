"""LangGraph 拓扑组装；节点做什么与节点如何连接分开维护。"""

from langgraph.graph import END, START, StateGraph

from aidahelp.agent.nodes import AgentNodes
from aidahelp.agent.routing import continue_agent, route_by_intent
from aidahelp.agent.state import AgentState


def build_workflow(nodes: AgentNodes, *, checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("understand", nodes.understand)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("answer", nodes.answer)
    builder.add_node("agent", nodes.agent)
    builder.add_node("tools", nodes.tools)
    builder.add_node("refund_flow", nodes.refund_flow)
    builder.add_node("human_flow", nodes.human_flow)

    builder.add_edge(START, "understand")
    builder.add_conditional_edges(
        "understand",
        route_by_intent,
        {
            "knowledge": "retrieve",
            "refund": "refund_flow",
            "human": "human_flow",
            "direct": "answer",
            "agent": "agent",
        },
    )
    builder.add_edge("retrieve", "answer")
    builder.add_edge("answer", END)
    builder.add_edge("refund_flow", END)
    builder.add_edge("human_flow", END)
    builder.add_conditional_edges(
        "agent",
        lambda state: continue_agent(state, nodes.settings.agent_max_steps),
        {"tools": "tools", "done": END},
    )
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)
