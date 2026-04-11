from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    """Get or create the MongoDB client."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_url)
    return _client


def get_database():
    """Get the application database."""
    return get_client()[settings.mongodb_database]


def get_collection(name: str):
    """Get a collection by name."""
    return get_database()[name]
