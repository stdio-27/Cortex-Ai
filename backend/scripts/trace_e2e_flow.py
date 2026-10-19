import asyncio
import httpx
import redis.asyncio as redis
from motor.motor_asyncio import AsyncIOMotorClient
import json
import time
import os

# Configuration (defaults to internal Docker compose URLs)
API_URL = os.getenv("API_URL", "http://localhost:8000/api/jobs")
REDIS_URI = os.getenv("REDIS_URI", "redis://redis:6379/0")
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://mongodb:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "research_copilot")

# Store timeline events
timeline = []
start_time = time.time()

def log_event(layer: str, summary: str):
    elapsed_ms = int((time.time() - start_time) * 1000)
    timeline.append({"time": f"+{elapsed_ms}ms", "layer": layer, "summary": summary})
    print(f"[{elapsed_ms}ms] [{layer}] {summary}")

async def check_celery_queue(redis_client, job_id: str):
    """
    Checks the Redis 'celery' list (default celery queue) to verify task arrival.
    We just check the length, as the message might be picked up immediately by the worker.
    """
    try:
        # Check standard celery queue
        llen = await redis_client.llen("celery")
        log_event("Redis Broker", f"Checked celery queue. Queue length: {llen}")
    except Exception as e:
        log_event("Redis Broker", f"Failed to check celery queue: {e}")

async def subscribe_to_job(redis_client, job_id: str):
    """
    Subscribes to the job's Redis Pub/Sub channel and yields events.
    """
    channel = f"job_updates:{job_id}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    log_event("Redis PubSub", f"Subscribed to channel {channel}")
    
    try:
        while True:
            # We use a short timeout loop so we can periodically yield control back
            try:
                message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
                if message:
                    data = message["data"].decode("utf-8")
                    try:
                        parsed = json.loads(data)
                        step = parsed.get("step", "UNKNOWN")
                        content = parsed.get("content", "")
                        # truncate content for summary if it's too long
                        content_summary = content[:50] + "..." if len(content) > 50 else content
                        content_summary = content_summary.replace("\n", " ") # clean up newlines for display
                        log_event("LangGraph Node", f"Event received: step={step}, content='{content_summary}'")
                        
                        if step in ["DONE", "ERROR"]:
                            log_event("LangGraph Node", f"Terminal state reached: {step}")
                            break
                        elif step == "AWAITING_HUMAN_FEEDBACK":
                            log_event("Client", "HITL Checkpoint reached. Auto-resuming with mock approved queries...")
                            async with httpx.AsyncClient() as client:
                                resume_res = await client.post(
                                    f"http://web:8000/api/jobs/{job_id}/resume", 
                                    json={"approved_queries": ["Mock sub-query 1", "Mock sub-query 2"]}
                                )
                                resume_res.raise_for_status()
                            log_event("FastAPI", "Sent POST to /api/jobs/{id}/resume successfully")
                    except json.JSONDecodeError:
                        log_event("LangGraph Node", f"Unparseable event received: {data}")
            except asyncio.TimeoutError:
                # Expected, continue loop to wait for next message
                pass
    finally:
        await pubsub.unsubscribe(channel)

async def verify_mongodb_state(mongo_client, job_id: str):
    """
    Verifies the final state in MongoDB.
    """
    db = mongo_client[MONGODB_DB_NAME]
    collection = db["jobs"]
    job = await collection.find_one({"job_id": job_id})
    
    if not job:
        log_event("MongoDB", f"Verification Failed: Job {job_id} not found in database.")
        return False
        
    status = job.get("status")
    output = job.get("synthesis_output", "")
    
    log_event("MongoDB", f"Job Document Found. Status: {status}")
    
    success = True
    if status != "COMPLETED":
        log_event("MongoDB", f"Verification Failed: Status is {status}, expected COMPLETED.")
        success = False
        
    if not output:
        log_event("MongoDB", f"Verification Failed: synthesis_output is empty.")
        success = False
    else:
        log_event("MongoDB", f"Verified synthesis_output exists (length: {len(output)})")
        
    return success

async def main():
    log_event("Client", "Starting E2E Tracer Script")
    
    redis_client = redis.from_url(REDIS_URI)
    mongo_client = AsyncIOMotorClient(MONGODB_URI)
    
    try:
        # Step 1: Send POST request
        log_event("Client", f"Sending POST request to {API_URL}")
        async with httpx.AsyncClient() as client:
            response = await client.post(API_URL, json={"query": "Trace architecture test query"})
            response.raise_for_status()
            data = response.json()
            job_id = data.get("job_id")
            log_event("FastAPI", f"Job created with ID: {job_id}")
            
        # Step 2: Confirm task arrival in celery
        await check_celery_queue(redis_client, job_id)
        
        # Step 3: Stream events with a global timeout to avoid hanging
        try:
            await asyncio.wait_for(subscribe_to_job(redis_client, job_id), timeout=60.0)
        except asyncio.TimeoutError:
            log_event("Redis PubSub", "Timed out waiting for job completion events.")
            
        # Wait a small moment to ensure MongoDB is fully updated after the final event
        await asyncio.sleep(1)
        
        # Step 4: Verify Database State
        log_event("Client", "Verifying final state in MongoDB")
        await verify_mongodb_state(mongo_client, job_id)
        
    except Exception as e:
        log_event("Client", f"An error occurred during tracing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await redis_client.aclose()
        mongo_client.close()
        
    # Step 5: Timeline Output
    print("\n" + "="*90)
    print("E2E ARCHITECTURE & DATA FLOW TRACE TIMELINE")
    print("="*90)
    print(f"{'Timestamp':<12} | {'Layer':<20} | {'Event & Payload Summary'}")
    print("-" * 90)
    for event in timeline:
        print(f"{event['time']:<12} | {event['layer']:<20} | {event['summary']}")
    print("="*90)

if __name__ == "__main__":
    asyncio.run(main())
