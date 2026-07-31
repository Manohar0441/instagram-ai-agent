from redis import Redis
from rq import Queue

from app.core.settings import settings

DEFAULT_QUEUE_NAME = "default"
DEFAULT_JOB_TIMEOUT_SECONDS = 180

_queue: Queue | None = None


def get_queue() -> Queue:
    """Return a lazily-created, process-wide RQ queue backed by Redis."""
    global _queue
    if _queue is None:
        connection = Redis.from_url(settings.REDIS_URL)
        _queue = Queue(DEFAULT_QUEUE_NAME, connection=connection)
    return _queue
