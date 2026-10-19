import json
import hashlib
from app.core.redis import get_redis_client
from app.core.config import settings
from app.agent.state import AgentState
from langchain_core.runnables import RunnableConfig
from tenacity import retry, stop_after_attempt, retry_if_exception

def _is_retryable(e: BaseException) -> bool:
    error_msg = str(e).lower()
    return "timeout" in error_msg or "connection" in error_msg or "50" in error_msg

# The global publish_update has been removed in favor of injected PubSubService
# LLM clients are now injected via LLMService
def planner_node(state: AgentState, config: RunnableConfig):
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
    return {"sub_topics": sub_topics}

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
        @retry(stop=stop_after_attempt(3), retry=retry_if_exception(_is_retryable), reraise=True)
        def _do_search():
            query_hash = hashlib.sha256(topic.encode()).hexdigest()
            cache_key = f"cache:search:{query_hash}"
            redis_client = get_redis_client()
            cached = redis_client.get(cache_key)
            if cached:
                if deps.pubsub:
                    deps.pubsub.publish_status(job_id, "search", {"step": "CACHE_HIT", "topic": topic})
                return json.loads(cached)
                
            res = deps.tavily.search(query=topic)
            redis_client.setex(cache_key, 86400, json.dumps(res))
            return res
            
        try:
            results = _do_search()
        except Exception as e:
            print(f"search_node: Exhausted attempts or non-retryable error for '{topic}': {e}. Degrading gracefully.")
            results = []
    else:
        results = []
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Search", "COMPLETED")
    return {"search_results": [{"topic": topic, "results": results}]}

def sanitization_node(state: AgentState, config: RunnableConfig):
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

def synthesizer_node(state: AgentState, config: RunnableConfig):
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

def verification_node(state: AgentState, config: RunnableConfig):
    deps = config.get("configurable", {}).get("deps")
    job_id = state.get("job_id")
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Verification", "IN_PROGRESS")
    
    draft = state.get("draft_report", "")
    search_results = state.get("search_results", [])
    
    if deps and deps.llm:
        verdict = deps.llm.verify_report(draft, search_results)
    else:
        verdict = {
            "verification_score": 100.0,
            "supported_claims_count": 0,
            "unverified_claims": [],
            "confidence_tier": "HIGH"
        }
    
    if deps and deps.pubsub:
        deps.pubsub.publish_update(job_id, "Verification", "COMPLETED")
        deps.pubsub.publish_status(
            job_id,
            "verification",
            {
                "status": "PROCESSING",
                "step": "VERIFICATION_COMPLETE",
                "verification_metadata": verdict,
            },
        )

    return {"verification_metadata": verdict}

def critique_node(state: AgentState, config: RunnableConfig):
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

