import pytest
import redis
from pydantic import BaseModel

from app.utils import cache

pytestmark = pytest.mark.unit


class Sample(BaseModel):
    value: str


class BrokenRedis:
    """A Redis client where every operation fails, as during an outage."""

    def get(self, key):
        raise redis.ConnectionError("redis is down")

    def setex(self, key, ttl, value):
        raise redis.ConnectionError("redis is down")


@pytest.fixture
def broken_redis(monkeypatch):
    monkeypatch.setattr(cache, "get_redis_client", lambda: BrokenRedis())


class TestCacheGetSet:
    def test_returns_none_on_miss(self, fake_redis):
        assert cache.cache_get("absent-key", Sample) is None

    def test_round_trips_a_model(self, fake_redis):
        cache.cache_set("k", Sample(value="hello"), 60)
        assert cache.cache_get("k", Sample) == Sample(value="hello")

    def test_sets_a_ttl(self, fake_redis):
        cache.cache_set("k", Sample(value="hello"), 60)
        assert 0 < fake_redis.ttl("k") <= 60

    def test_treats_a_corrupt_entry_as_a_miss(self, fake_redis):
        """A cached value that no longer matches the schema (e.g. left over
        from an older deploy) must not break the request."""
        fake_redis.set("k", '{"unexpected": "shape"}')
        assert cache.cache_get("k", Sample) is None


class TestCacheFailsOpen:
    def test_read_failure_is_a_miss_not_an_error(self, broken_redis):
        assert cache.cache_get("k", Sample) is None

    def test_write_failure_does_not_raise(self, broken_redis):
        cache.cache_set("k", Sample(value="hello"), 60)  # must not raise

    def test_generation_still_happens_when_redis_is_down(self, broken_redis):
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
    def test_generates_and_stores_on_miss(self, fake_redis):
        result = cache.get_or_generate("k", Sample, 60, lambda: Sample(value="fresh"))
        assert result == Sample(value="fresh")
        assert cache.cache_get("k", Sample) == Sample(value="fresh")

    def test_does_not_regenerate_on_hit(self, fake_redis):
        calls = []

        def generate():
            calls.append(1)
            return Sample(value="fresh")

        cache.get_or_generate("k", Sample, 60, generate)
        cache.get_or_generate("k", Sample, 60, generate)
        assert len(calls) == 1
