import logging
import time
from collections.abc import Callable
from typing import TypeVar

from botocore.exceptions import ClientError
from pydantic import BaseModel, ValidationError

from app.integrations.dynamodb_client import get_cache_table

logger = logging.getLogger("app.cache")

T = TypeVar("T", bound=BaseModel)


def cache_get(key: str, schema: type[T]) -> T | None:
    """Return a cached Pydantic model, or None on a miss/expired/corrupt entry/DynamoDB error.

    Caching is a performance optimization, never a hard dependency - any
    DynamoDB failure here is logged and treated as a miss so the caller falls
    back to generating fresh data instead of failing the request.
    """
    try:
        response = get_cache_table().get_item(Key={"cache_key": key})
    except ClientError as exc:
        logger.warning("cache read failed, generating fresh", extra={"cache_key": key, "error": str(exc)})
        return None

    item = response.get("Item")
    if item is None:
        return None

    # DynamoDB's TTL deletion is best-effort (up to 48h after expiry), so an
    # expired item can still be returned here - check it ourselves rather
    # than trusting the table to have removed it already.
    if int(item["expires_at"]) <= int(time.time()):
        return None

    try:
        return schema.model_validate_json(item["value"])
    except ValidationError:
        logger.warning("cache entry failed validation, generating fresh", extra={"cache_key": key})
        return None


def cache_set(key: str, value: BaseModel, ttl_seconds: int) -> None:
    """Store a Pydantic model with a TTL. Failures are logged, never raised."""
    try:
        get_cache_table().put_item(
            Item={
                "cache_key": key,
                "value": value.model_dump_json(),
                "expires_at": int(time.time()) + ttl_seconds,
            }
        )
    except ClientError as exc:
        logger.warning("cache write failed, continuing without caching", extra={"cache_key": key, "error": str(exc)})


def get_or_generate(key: str, schema: type[T], ttl_seconds: int, generate: Callable[[], T]) -> T:
    """Return a cached value if present, otherwise generate, cache, and return it."""
    cached = cache_get(key, schema)
    if cached is not None:
        return cached

    result = generate()
    cache_set(key, result, ttl_seconds)
    return result
