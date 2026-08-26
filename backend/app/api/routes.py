from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.job import JobRequest, JobResponse, Job
from app.db.mongodb import db
from app.core.config import settings
from app.worker.celery_app import celery_app
import uuid
import asyncio
from app.core.redis import get_async_redis_client
import json

router = APIRouter()

@router.post("/jobs", response_model=JobResponse)
async def create_job(request: JobRequest):
    try:
        job_id = str(uuid.uuid4())
        
        job_data = Job(
            job_id=job_id,
            query=request.query
        )
        
        # Save to MongoDB
        await db.client[settings.MONGODB_DB_NAME]["jobs"].insert_one(job_data.model_dump())
        
        # Enqueue Celery task by name (avoids importing the full agent chain)
        celery_app.send_task('process_job', args=[job_id])
        
        return JobResponse(job_id=job_id, status="PENDING")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")

@router.get("/jobs/{job_id}/stream")
async def stream_job_updates(job_id: str):
    async def event_generator():
        redis_client = get_async_redis_client()
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"job_updates:{job_id}")
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = message["data"].decode("utf-8")
                    yield f"data: {data}\n\n"
                    
                    parsed = json.loads(data)
                    if parsed.get("step") in ["DONE", "ERROR"]:
                        break
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(f"job_updates:{job_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.client[settings.MONGODB_DB_NAME]["jobs"].find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Exclude the MongoDB internal _id field from the response
    if "_id" in job:
        del job["_id"]
        
    return job
