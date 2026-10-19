from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from app.core.config import settings

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
