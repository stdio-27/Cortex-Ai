import json
import asyncio
from app.db.mongo import db
from app.core.config import settings
from app.agent.graph import get_compiled_graph
from langgraph.checkpoint.mongodb import MongoDBSaver
from app.schemas.events import SystemEventV1
from app.services.pubsub_service import PubSubService

async def run_agent(job_id: str, resume_data: dict = None):
    from app.core.redis import get_redis_client, get_redis_pubsub_client
    redis_client = get_redis_client()
    pubsub_client = get_redis_pubsub_client()
    try:
        jobs_collection = db.sync_client[settings.MONGODB_DB_NAME]["jobs"]
        
        job = jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise ValueError(f"Job {job_id} not found")
            
        if job.get("status") in ["COMPLETED", "FAILED"]:
            print(f"Job {job_id} is already {job.get('status')}. Discarding duplicate processing.")
            return

        result = jobs_collection.update_one(
            {"job_id": job_id, "status": {"$in": ["PENDING", "PROCESSING", "RESUMING", "AWAITING_INPUT", None]}},
            {"$set": {"status": "PROCESSING"}}
        )
        if result.modified_count == 0 and result.matched_count == 0:
            print(f"Job {job_id} could not transition to PROCESSING. Discarding.")
            return
            
        if resume_data:
            print(f"Job {job_id} resumed. Status updated to PROCESSING")
        else:
            print(f"Job {job_id} started. Status updated to PROCESSING")
            
        initial_state = {
            "job_id": job_id,
            "query": job["query"],
            "sub_topics": [],
            "search_results": [],
            "sanitized_content": "",
            "draft_report": "",
            "critique": "",
            "iteration_count": 0
        }
        
        from app.services.tavily_service import TavilyService, MockTavilyService
        from app.services.llm_service import LLMService, MockLLMService
        from app.services.deps import Deps
        from tavily import TavilyClient
        
        if settings.MOCK_LLM_FOR_LOAD_TEST:
            tavily_service = MockTavilyService()
            llm_service = MockLLMService()
        else:
            tavily_service = TavilyService(TavilyClient(api_key=settings.TAVILY_API_KEY))
            llm_service = LLMService(
                groq_model=settings.GROQ_MODEL,
                groq_fast_model=settings.GROQ_FAST_MODEL,
                api_key=settings.GROQ_API_KEY
            )
        
        deps = Deps(
            pubsub_service=PubSubService(pubsub_client),
            tavily_service=tavily_service,
            llm_service=llm_service
        )
        
        # Checkpointer setup
        checkpointer = MongoDBSaver(db.sync_client)
        agent_graph = get_compiled_graph(checkpointer)
        
        config = {
            "configurable": {
                "thread_id": job_id,
                "deps": deps
            },
            "recursion_limit": 25
        }
        
        if resume_data:
            # Only apply the approved queries while the graph is still paused before
            # "search"; on a Celery retry the graph is already past that point and
            # must simply continue from its last checkpoint.
            snapshot = agent_graph.get_state(config)
            if "search" in (snapshot.next or ()):
                approved_queries = resume_data.get("approved_queries", [])
                agent_graph.update_state(config, {"sub_topics": approved_queries})
            final_state = await agent_graph.ainvoke(None, config)
        else:
            state_snapshot = agent_graph.get_state(config)
            if state_snapshot.next:
                # Graph was interrupted and not resumed correctly via API, just resume as is
                final_state = await agent_graph.ainvoke(None, config)
            else:
                # Start new execution
                final_state = await agent_graph.ainvoke(initial_state, config)
                
        # Check if the graph execution was paused (interrupted)
        current_state = agent_graph.get_state(config)
        if current_state.next and "search" in current_state.next:
            # Paused before search, awaiting human feedback
            jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": {"status": "AWAITING_INPUT"}}
            )
            event = SystemEventV1(
                job_id=job_id,
                event_type="AWAITING_INPUT",
                stage="planner",
                data={
                    "step": "AWAITING_HUMAN_FEEDBACK",
                    "sub_topics": final_state.get("sub_topics", []),
                    "status": "AWAITING_INPUT"
                }
            )
            PubSubService(pubsub_client).publish_event(event)
            print(f"Job {job_id} paused awaiting human feedback.")
            return
        
        draft_report = final_state.get("draft_report", "")
        verification_metadata = final_state.get("verification_metadata", {})
        
        # 3. Update status to COMPLETED and save report
        jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "COMPLETED", 
                "report": draft_report,
                "verification_metadata": verification_metadata
            }}
        )
        print(f"Job {job_id} status updated to COMPLETED")
        
        event = SystemEventV1(
            job_id=job_id,
            event_type="COMPLETED",
            stage="finished",
            data={"step": "DONE", "status": "COMPLETED"}
        )
        PubSubService(pubsub_client).publish_event(event)
        
    except Exception as e:
        # Do NOT swallow: the Celery task decides between retry (429/transient)
        # and terminal failure. Terminal failures are marked FAILED, published
        # to the UI and dead-lettered by the task_failure hook in worker/tasks.py.
        print(f"Error processing job {job_id}: {type(e).__name__}: {e}")
        raise
