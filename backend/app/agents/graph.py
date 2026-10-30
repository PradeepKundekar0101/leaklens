"""The claim orchestrator.

load_claim -> document -> load_policy -> (rules | anomaly | coverage x N) -> join -> route
  -> [investigate (high risk only)] -> decide -> human_review (interrupt) -> finalize
"""

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import analysis, decision, intake
from app.agents.state import ClaimState


def build_graph() -> StateGraph:
    g = StateGraph(ClaimState)
    g.add_node("load_claim", intake.load_claim)
    g.add_node("document", intake.document)
    g.add_node("load_policy", intake.load_policy)
    g.add_node("rules", analysis.rules)
    g.add_node("anomaly", analysis.anomaly)
    g.add_node("coverage", analysis.coverage)
    g.add_node("join", analysis.join)
    g.add_node("investigate", decision.investigate)
    g.add_node("decide", decision.decide)
    g.add_node("human_review", decision.human_review)
    g.add_node("finalize", decision.finalize)

    g.add_edge(START, "load_claim")
    g.add_edge("load_claim", "document")
    g.add_edge("document", "load_policy")
    g.add_conditional_edges("load_policy", analysis.fan_out, ["rules", "anomaly", "coverage"])
    g.add_edge("rules", "join")
    g.add_edge("anomaly", "join")
    g.add_edge("coverage", "join")
    g.add_conditional_edges("join", analysis.route, {"investigate": "investigate", "decide": "decide"})
    g.add_edge("investigate", "decide")
    g.add_edge("decide", "human_review")
    g.add_edge("human_review", "finalize")
    g.add_edge("finalize", END)
    return g
