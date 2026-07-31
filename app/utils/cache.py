import logging
from collections.abc import Callable
from typing import TypeVar

import redis
from pydantic import BaseModel, ValidationError

from app.integrations.redis_client import get_redis_client

logger = logging.getLogger("app.cache")

T = TypeVar("T", bound=BaseModel)


def cache_get(key: str, schema: type[T]) -> T | None:
    """Return a cached Pydantic model, or None on a miss/corrupt entry/Redis error.

    Caching is a performance optimization, never a hard dependency - any
    Redis failure here is logged and treated as a miss so the caller falls
    back to generating fresh data instead of failing the request.
    """
    try:
        raw = get_redis_client().get(key)
    except redis.RedisError as exc:
        logger.warning("cache read failed, generating fresh", extra={"cache_key": key, "error": str(exc)})
        return None

    if raw is None:
        return None

    try:
        return schema.model_validate_json(raw)
    except ValidationError:
        logger.warning("cache entry failed validation, generating fresh", extra={"cache_key": key})
        return None


def cache_set(key: str, value: BaseModel, ttl_seconds: int) -> None:
    """Store a Pydantic model with a TTL. Failures are logged, never raised."""
    try:
        get_redis_client().setex(key, ttl_seconds, value.model_dump_json())
    except redis.RedisError as exc:
        logger.warning("cache write failed, continuing without caching", extra={"cache_key": key, "error": str(exc)})


def get_or_generate(key: str, schema: type[T], ttl_seconds: int, generate: Callable[[], T]) -> T:
    """Return a cached value if present, otherwise generate, cache, and return it."""
    cached = cache_get(key, schema)
    if cached is not None:
        return cached

    result = generate()
    cache_set(key, result, ttl_seconds)
    return result
