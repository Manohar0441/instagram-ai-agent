import redis

from app.core.settings import settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Return a lazily-created, process-wide Redis client."""
    global _client
    if _client is None:
        _client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
