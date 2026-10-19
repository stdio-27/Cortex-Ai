import redis
import redis.asyncio as aioredis
from app.core.config import settings

# Sync pool for celery/nodes
sync_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URI, 
    max_connections=20,
    health_check_interval=30,
    socket_timeout=5.0
)

# Async pool for FastAPI
async_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URI, 
    max_connections=100,
    health_check_interval=30,
    socket_timeout=5.0
)

# Sync pool for pub/sub
pubsub_sync_pool = redis.ConnectionPool.from_url(
    settings.REDIS_PUBSUB_URI, 
    max_connections=20,
    health_check_interval=30,
    socket_timeout=5.0
)

# Async pool for FastAPI pub/sub (SSE)
pubsub_async_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_PUBSUB_URI, 
    max_connections=100,
    health_check_interval=30,
    socket_timeout=5.0
)

def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=sync_pool)

def get_async_redis_client() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=async_pool)

def get_redis_pubsub_client() -> redis.Redis:
    return redis.Redis(connection_pool=pubsub_sync_pool)

def get_async_redis_pubsub_client() -> aioredis.Redis:
    return aioredis.Redis(connection_pool=pubsub_async_pool)
