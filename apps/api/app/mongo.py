from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_mongo() -> AsyncIOMotorDatabase:
    return get_client()[settings.mongo_db]


async def ensure_indexes() -> None:
    db = get_mongo()
    await db.events.create_index([("user_id", 1), ("ts", -1)])
    await db.events.create_index([("video_id", 1), ("ts", -1)])
    await db.events.create_index([("event_type", 1), ("ts", -1)])
    await db.events.create_index([("campaign_id", 1), ("ts", -1)])
    await db.user_profiles_online.create_index("user_id", unique=True)
    await db.ranking_traces.create_index([("user_id", 1), ("ts", -1)])
    await db.events.create_index("event_id", unique=True, partialFilterExpression={"event_id": {"$type": "string"}})
    await db.events.create_index([("exposure_id", 1), ("ts", 1)])
    await db.exposures.create_index([("campaign_id", 1), ("started_at", -1)])
    await db.exposures.create_index([("user_id", 1), ("session_id", 1), ("started_at", 1)])
    await db.decisions.create_index("expires_at", expireAfterSeconds=0)


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
