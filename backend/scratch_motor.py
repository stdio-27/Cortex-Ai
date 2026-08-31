import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient("mongodb://localhost:27017")

async def test1():
    db = client.test_db
    await db.test_coll.find_one()
    print("Test 1 done")

async def test2():
    db = client.test_db
    await db.test_coll.find_one()
    print("Test 2 done")

def main():
    asyncio.run(test1())
    asyncio.run(test2())

if __name__ == "__main__":
    main()
