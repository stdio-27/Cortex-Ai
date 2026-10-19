from fastapi import FastAPI
from app.api.routes import router
from app.db.mongo import connect_to_mongo, close_mongo_connection, ensure_indexes, db
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await ensure_indexes()
    app.state.mongo_client = db.async_client
    yield
    app.state.mongo_client.close()
    # close_mongo_connection() could also be called, but the spec explicitly requested app.state.mongo_client.close()

app = FastAPI(
    title="Autonomous Research Copilot",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to Autonomous Research Copilot API"}
