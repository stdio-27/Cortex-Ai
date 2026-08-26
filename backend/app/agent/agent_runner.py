import json
import asyncio
from app.db.mongodb import db, connect_to_mongo, close_mongo_connection
from app.core.config import settings
from app.agent.graph import agent_graph

async def run_agent(job_id: str):
    # Connect to DB in the worker process
    await connect_to_mongo()
    from app.core.redis import get_redis_client
    redis_client = get_redis_client()
    try:
        jobs_collection = db.client[settings.MONGODB_DB_NAME]["jobs"]
        
        # 1. Update status to PROCESSING
        await jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"status": "PROCESSING"}}
        )
        print(f"Job {job_id} status updated to PROCESSING")
        
        job = await jobs_collection.find_one({"job_id": job_id})
        if not job:
            raise ValueError(f"Job {job_id} not found")
            
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
        
        # Run LangGraph pipeline
        final_state = await asyncio.to_thread(
            agent_graph.invoke,
            initial_state,
            {"recursion_limit": 25}
        )
        
        draft_report = final_state.get("draft_report", "")
        
        # 3. Update status to COMPLETED and save report
        await jobs_collection.update_one(
            {"job_id": job_id},
            {"$set": {"status": "COMPLETED", "report": draft_report}}
        )
        print(f"Job {job_id} status updated to COMPLETED")
        
        redis_client.publish(
            f"job_updates:{job_id}",
            json.dumps({"job_id": job_id, "status": "COMPLETED", "step": "DONE"})
        )
        
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        try:
            await jobs_collection.update_one(
                {"job_id": job_id},
                {"$set": {"status": "FAILED"}}
            )
            redis_client.publish(
                f"job_updates:{job_id}",
                json.dumps({"job_id": job_id, "status": "FAILED", "step": "ERROR"})
            )
        except Exception as inner_e:
            print(f"Inner error: {inner_e}")
    finally:
        await close_mongo_connection()
