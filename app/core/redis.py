# app/core/redis.py

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


async def init_redis() -> Redis | None:
    global _redis_client  # noqa: PLW0603
    if settings.testing or settings.redis_url == "memory://":
        return None
    _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    global _redis_client  # noqa: PLW0603
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialized")
    return _redis_client


def get_redis_optional() -> Redis | None:
    """Return the live Redis client, or ``None`` when unavailable (e.g. tests)."""
    return _redis_client
