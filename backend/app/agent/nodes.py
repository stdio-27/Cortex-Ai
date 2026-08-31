import json
import time
from app.core.redis import get_redis_client
from app.core.config import settings
from app.agent.state import AgentState
# Langchain imports moved to LLMService
# Tavily Client import removed (moved to service)

from langchain_core.runnables import RunnableConfig

# The global publish_update has been removed in favor of injected PubSubService

# LLM clients are now injected via LLMService
from typing import TypedDict, List

class PlannerState(TypedDict, total=False):
    job_id: str
    query: str
    iteration_count: int

def planner_node(state: PlannerState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Planner", "IN_PROGRESS")
    
    query = state["query"]
    
    if deps and deps.llm:
        sub_topics = deps.llm.generate_sub_topics(query)
    else:
        sub_topics = []
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Planner", "COMPLETED")
    return {"sub_topics": sub_topics, "iteration_count": state.get("iteration_count", 0)}

from typing import TypedDict

class SubTopicState(TypedDict):
    topic: str
    job_id: str

def search_node(state: SubTopicState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    topic = state.get("topic")
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Search", "IN_PROGRESS")
    
    if deps and deps.tavily:
        results = deps.tavily.search(query=topic, search_depth="basic", max_results=3)
    else:
        results = []
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Search", "COMPLETED")
    return {"search_results": [{"topic": topic, "results": results}]}

class SanitizationState(TypedDict, total=False):
    job_id: str
    search_results: list

def sanitization_node(state: SanitizationState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    # We do not have a specific UI step for Sanitization in the frontend graph, 
    # but we can emit IN_PROGRESS for Synthesizing early, or just don't emit UI event for Sanitization 
    # since it's an intermediate step. We will just do it silently.
    
    raw_results = state.get("search_results", [])
    
    if deps and deps.llm:
        sanitized = deps.llm.sanitize_search_results(raw_results)
    else:
        sanitized = ""
    
    return {"sanitized_content": sanitized}

class SynthesizerState(TypedDict, total=False):
    job_id: str
    query: str
    sanitized_content: str
    critique: str
    iteration_count: int

def synthesizer_node(state: SynthesizerState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Synthesizing", "IN_PROGRESS")
    
    query = state["query"]
    sanitized = state.get("sanitized_content", "")
    critique = state.get("critique", "")
    
    if deps and deps.llm:
        draft = deps.llm.synthesize_report(query, sanitized, critique)
    else:
        draft = ""
    
    iteration_count = state.get("iteration_count", 0) + 1
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Synthesizing", "COMPLETED")
    return {"draft_report": draft, "iteration_count": iteration_count}

class CritiqueState(TypedDict, total=False):
    job_id: str
    query: str
    draft_report: str

def critique_node(state: CritiqueState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Critiquing", "IN_PROGRESS")
    
    query = state["query"]
    draft = state.get("draft_report", "")
    
    if deps and deps.llm:
        critique = deps.llm.critique_report(query, draft)
    else:
        critique = "APPROVED"
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Critiquing", "COMPLETED")
    return {"critique": critique}

