import redis
import redis.asyncio as aioredis
from app.core.config import settings

# Sync pool for celery/nodes
sync_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URI, 
    max_connections=2000
)

# Async pool for FastAPI
async_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URI, 
    max_connections=2000
)

def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=sync_pool)

def get_async_redis_client() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=async_pool)
