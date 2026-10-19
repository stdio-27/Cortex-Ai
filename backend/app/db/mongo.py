from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

DLQ_RETENTION_SECONDS = 90 * 24 * 3600

class MongoDB:
    async_client: AsyncIOMotorClient = None
    sync_client: MongoClient = None

db = MongoDB()

async def connect_to_mongo():
    db.async_client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        minPoolSize=5,
        maxPoolSize=20,
        maxIdleTimeMS=45000,
        serverSelectionTimeoutMS=5000
    )
    print("Connected to MongoDB (Async)")

async def close_mongo_connection():
    if db.async_client:
        db.async_client.close()
        print("Closed MongoDB connection (Async)")

async def ensure_indexes() -> None:
    """Create the indexes the hot paths rely on (idempotent, safe with N API workers).

    Without `jobs.job_id` every lookup by job id is a full collection scan.
    Failure is logged, not fatal: the API still works, just slower.
    """
    try:
        database = db.async_client[settings.MONGODB_DB_NAME]
        await database["jobs"].create_index("job_id", unique=True, name="uniq_job_id")
        await database["dead_letter_jobs"].create_index("task_id", unique=True, name="uniq_task_id")
        await database["dead_letter_jobs"].create_index("job_id", name="idx_job_id")
        await database["dead_letter_jobs"].create_index(
            "failed_at_dt", expireAfterSeconds=DLQ_RETENTION_SECONDS, name="ttl_failed_at"
        )
        logger.info("MongoDB indexes ensured")
    except Exception as exc:
        logger.warning("Could not ensure MongoDB indexes: %s", exc)

def connect_to_mongo_sync():
    db.sync_client = MongoClient(
        settings.MONGODB_URI,
        minPoolSize=5,
        maxPoolSize=20,
        maxIdleTimeMS=45000,
        serverSelectionTimeoutMS=5000
    )
    print("Connected to MongoDB (Sync)")

def close_mongo_connection_sync():
    if db.sync_client:
        db.sync_client.close()
        print("Closed MongoDB connection (Sync)")
