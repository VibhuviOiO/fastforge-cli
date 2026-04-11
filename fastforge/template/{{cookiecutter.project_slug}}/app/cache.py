"""Cache client — {{ cookiecutter.cache }} backend."""
{%- if cookiecutter.cache == "redis" %}

import redis.asyncio as redis

from app.config import settings

_client: redis.Redis | None = None


async def get_cache() -> redis.Redis:
    """Get the Redis cache client (lazy init)."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_cache() -> None:
    """Close the Redis connection pool."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.aclose()
        _client = None
{%- elif cookiecutter.cache == "memcached" %}

import aiomcache

from app.config import settings

_client: aiomcache.Client | None = None


def get_cache() -> aiomcache.Client:
    """Get the Memcached client (lazy init)."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = aiomcache.Client(settings.memcached_host, settings.memcached_port)
    return _client


async def close_cache() -> None:
    """Close the Memcached connection."""
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
        _client = None
{%- elif cookiecutter.cache == "in_memory" %}

from cachetools import TTLCache

_cache: TTLCache = TTLCache(maxsize=1024, ttl=300)


def get_cache() -> TTLCache:
    """Get the in-memory TTL cache (1024 items, 5 min TTL)."""
    return _cache


async def close_cache() -> None:
    """Clear the in-memory cache."""
    _cache.clear()
{%- endif %}
