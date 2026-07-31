"""Entrypoint for the RQ background worker process.

Run with: python -m app.worker
"""
from redis import Redis
from rq import Worker

from app.core.logging import configure_logging
from app.core.settings import settings
from app.integrations.task_queue import DEFAULT_QUEUE_NAME


def main() -> None:
    configure_logging()
    connection = Redis.from_url(settings.REDIS_URL)
    worker = Worker([DEFAULT_QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
