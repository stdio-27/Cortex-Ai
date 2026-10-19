from typing import Annotated
from langgraph.graph import END, StateGraph  # type: ignore[reportMissingImports]
from langgraph.types import Send  # type: ignore[reportMissingImports]
from app.agent.state import AgentState
from app.agent.nodes import (
    planner_node,
    search_node,
    sanitization_node,
    synthesizer_node,
    critique_node,
    SubTopicState
)

def continue_to_search(state: AgentState):
    # Fan out to search_node for each sub_topic
    job_id = state.get("job_id")
    sub_topics = state.get("sub_topics", [])
    return [Send("search", {"topic": t, "job_id": job_id}) for t in sub_topics]

def should_continue(state: AgentState):
    critique = state.get("critique", "").strip().upper()
    iteration_count = state.get("iteration_count", 0)
    
    # Circuit breaker: max 2 iterations or approved
    if "APPROVED" in critique or iteration_count >= 2:
        return END
    return "synthesizer"

# Build Graph
builder = StateGraph(AgentState)

from app.agent.nodes import verification_node

builder.add_node("planner", planner_node)
builder.add_node("search", search_node)
builder.add_node("sanitization", sanitization_node)
builder.add_node("synthesizer", synthesizer_node)
builder.add_node("verification", verification_node)
builder.add_node("critique", critique_node)

builder.set_entry_point("planner")
builder.add_conditional_edges("planner", continue_to_search, ["search"])
builder.add_edge("search", "sanitization")
builder.add_edge("sanitization", "synthesizer")
builder.add_edge("synthesizer", "verification")
builder.add_edge("verification", "critique")
builder.add_conditional_edges(
    "critique",
    should_continue,
    {
        END: END,
        "synthesizer": "synthesizer"
    }
)

def get_compiled_graph(checkpointer=None):
    return builder.compile(checkpointer=checkpointer, interrupt_before=["search"])
