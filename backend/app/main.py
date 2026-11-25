import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.core.config import settings
from app.core.redis import get_async_redis_client, get_async_redis_pubsub_client
from app.db.mongo import connect_to_mongo, ensure_indexes, db
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    app.state.mongo_client = db.async_client
    try:
        await ensure_indexes()
        yield
    finally:
        app.state.mongo_client.close()

app = FastAPI(
    title="Autonomous Research Copilot",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}

@app.get("/api/health/ready", include_in_schema=False)
async def readiness():
    try:
        async with asyncio.timeout(5):
            await asyncio.gather(
                db.async_client.admin.command("ping"),
                get_async_redis_client().ping(),
                get_async_redis_pubsub_client().ping(),
            )
    except Exception as exc:
        logger.warning("Readiness check failed: %s", type(exc).__name__)
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}

@app.get("/")
async def root():
    return {"message": "Welcome to Autonomous Research Copilot API"}
