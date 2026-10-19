from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.job import JobRequest, JobResponse, Job
from app.db.mongo import db
from app.core.config import settings
from app.worker.celery_app import celery_app
import uuid
from app.core.redis import get_async_redis_pubsub_client
import json
import logging

from pydantic import BaseModel
from app.schemas.events import job_channel
from app.services.pubsub_service import LAST_EVENT_KEY_PREFIX

logger = logging.getLogger(__name__)

TERMINAL_EVENT_TYPES = ("COMPLETED", "ERROR")

class ResumeRequest(BaseModel):
    approved_queries: list[str]
    custom_urls: list[str] | None = None

router = APIRouter()

@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str, request: ResumeRequest):
    try:
        # Drop the stale AWAITING_INPUT snapshot so the reconnecting SSE client
        # isn't replayed the pause it just answered.
        try:
            await get_async_redis_pubsub_client().delete(f"{LAST_EVENT_KEY_PREFIX}{job_id}")
        except Exception as exc:
            logger.warning("Could not clear last event for job %s: %s", job_id, exc)

        # Enqueue Celery task and pass resume_data
        celery_app.send_task('process_job', args=[job_id, request.model_dump()])
        return {"job_id": job_id, "status": "RESUMING"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to resume job: {str(e)}")

@router.post("/jobs", response_model=JobResponse)
async def create_job(request: JobRequest):
    try:
        job_id = str(uuid.uuid4())
        
        job_data = Job(
            job_id=job_id,
            query=request.query
        )
        
        # Save to MongoDB
        await db.async_client[settings.MONGODB_DB_NAME]["jobs"].insert_one(job_data.model_dump())
        
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
        redis_client = get_async_redis_pubsub_client()
        pubsub = redis_client.pubsub()
        # Subscribe BEFORE reading the snapshot: anything published after this
        # point is delivered live, anything before it is in the snapshot. Doing
        # it the other way round would leave a gap where events are lost.
        await pubsub.subscribe(job_channel(job_id))

        try:
            replayed = None
            try:
                snapshot = await redis_client.get(f"{LAST_EVENT_KEY_PREFIX}{job_id}")
            except Exception as exc:
                logger.warning("Could not read last event for job %s: %s", job_id, exc)
                snapshot = None

            if snapshot:
                replayed = snapshot.decode("utf-8") if isinstance(snapshot, bytes) else snapshot
                try:
                    replay_type = json.loads(replayed).get("event_type")
                except (ValueError, AttributeError):
                    replayed, replay_type = None, None
                if replayed:
                    yield f"data: {replayed}\n\n"
                    if replay_type in TERMINAL_EVENT_TYPES:
                        return

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    data = message["data"]
                    data = data.decode("utf-8") if isinstance(data, bytes) else data
                    # The event we just replayed may also arrive live (published
                    # between subscribe and GET); don't send it twice.
                    if data == replayed:
                        replayed = None
                        continue
                    yield f"data: {data}\n\n"

                    parsed = json.loads(data)
                    if parsed.get("event_type") in TERMINAL_EVENT_TYPES:
                        break
        finally:
            await pubsub.unsubscribe(job_channel(job_id))

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.async_client[settings.MONGODB_DB_NAME]["jobs"].find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Exclude the MongoDB internal _id field from the response
    if "_id" in job:
        del job["_id"]
        
    return job
