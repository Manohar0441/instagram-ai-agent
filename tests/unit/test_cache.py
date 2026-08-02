import time

import pytest
from botocore.exceptions import ClientError
from pydantic import BaseModel

from app.utils import cache

pytestmark = pytest.mark.unit


class Sample(BaseModel):
    value: str


class BrokenTable:
    """A DynamoDB table where every operation fails, as during an outage."""

    def get_item(self, **kwargs):
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "down"}}, "GetItem")

    def put_item(self, **kwargs):
        raise ClientError({"Error": {"Code": "InternalServerError", "Message": "down"}}, "PutItem")


@pytest.fixture
def broken_table(monkeypatch):
    monkeypatch.setattr(cache, "get_cache_table", lambda: BrokenTable())


class TestCacheGetSet:
    def test_returns_none_on_miss(self, fake_dynamodb):
        assert cache.cache_get("absent-key", Sample) is None

    def test_round_trips_a_model(self, fake_dynamodb):
        cache.cache_set("k", Sample(value="hello"), 60)
        assert cache.cache_get("k", Sample) == Sample(value="hello")

    def test_sets_a_ttl_in_the_future(self, fake_dynamodb):
        cache.cache_set("k", Sample(value="hello"), 60)
        item = fake_dynamodb.get_item(TableName="instalysis-cache", Key={"cache_key": {"S": "k"}})["Item"]
        expires_at = int(item["expires_at"]["N"])
        assert time.time() < expires_at <= time.time() + 60

    def test_treats_an_expired_entry_as_a_miss(self, fake_dynamodb):
        """DynamoDB's own TTL deletion is best-effort and can lag - the app
        must not trust a stale expires_at just because the item is still
        physically present."""
        fake_dynamodb.put_item(
            TableName="instalysis-cache",
            Item={
                "cache_key": {"S": "k"},
                "value": {"S": Sample(value="stale").model_dump_json()},
                "expires_at": {"N": str(int(time.time()) - 10)},
            },
        )
        assert cache.cache_get("k", Sample) is None

    def test_treats_a_corrupt_entry_as_a_miss(self, fake_dynamodb):
        """A cached value that no longer matches the schema (e.g. left over
        from an older deploy) must not break the request."""
        fake_dynamodb.put_item(
            TableName="instalysis-cache",
            Item={
                "cache_key": {"S": "k"},
                "value": {"S": '{"unexpected": "shape"}'},
                "expires_at": {"N": str(int(time.time()) + 60)},
            },
        )
        assert cache.cache_get("k", Sample) is None


class TestCacheFailsOpen:
    def test_read_failure_is_a_miss_not_an_error(self, broken_table):
        assert cache.cache_get("k", Sample) is None

    def test_write_failure_does_not_raise(self, broken_table):
        cache.cache_set("k", Sample(value="hello"), 60)  # must not raise

    def test_generation_still_happens_when_dynamodb_is_down(self, broken_table):
        """Caching is an optimization; an outage must degrade to
        regenerating, never to failing the request."""
        calls = []

        def generate():
            calls.append(1)
            return Sample(value="generated")

        result = cache.get_or_generate("k", Sample, 60, generate)
        assert result == Sample(value="generated")
        assert len(calls) == 1


class TestGetOrGenerate:
    def test_generates_and_stores_on_miss(self, fake_dynamodb):
        result = cache.get_or_generate("k", Sample, 60, lambda: Sample(value="fresh"))
        assert result == Sample(value="fresh")
        assert cache.cache_get("k", Sample) == Sample(value="fresh")

    def test_does_not_regenerate_on_hit(self, fake_dynamodb):
        calls = []

        def generate():
            calls.append(1)
            return Sample(value="fresh")

        cache.get_or_generate("k", Sample, 60, generate)
        cache.get_or_generate("k", Sample, 60, generate)
        assert len(calls) == 1
