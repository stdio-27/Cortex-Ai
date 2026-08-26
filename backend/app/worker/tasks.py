from app.worker.celery_app import celery_app
from app.agent.agent_runner import run_agent
import asyncio

@celery_app.task(name="process_job")
def process_job(job_id: str):
    print(f"Starting job {job_id} processing in Celery worker.")
    # Run the async agent runner
    asyncio.run(run_agent(job_id))
    return {"job_id": job_id, "status": "COMPLETED"}
