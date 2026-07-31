from typing import Literal

from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.integrations.task_queue import DEFAULT_JOB_TIMEOUT_SECONDS
from app.schemas.jobs import JobStatusResponse
from app.workers.jobs import generate_report_job


class JobServiceError(Exception):
    """Base exception for background job failures."""


class JobNotFoundError(JobServiceError):
    """Raised when a job ID doesn't exist or doesn't belong to the requesting user."""


class JobService:
    """Enqueue and check the status of background jobs.

    Every job is tagged with the requesting user's ID in its metadata, so
    get_job_status can refuse to return another user's job - a user who
    guesses or reuses a job ID they don't own gets the same "not found"
    response as a genuinely unknown ID, rather than a distinguishing 403.
    """

    def __init__(self, queue: Queue) -> None:
        """Initialize the service with its RQ queue dependency."""
        self.queue = queue

    def enqueue_report_generation(self, user_id: int, period: Literal["weekly", "monthly"]) -> str:
        """Queue background generation of a weekly/monthly report; return the job ID."""
        job = self.queue.enqueue(
            generate_report_job,
            user_id,
            period,
            meta={"user_id": user_id},
            job_timeout=DEFAULT_JOB_TIMEOUT_SECONDS,
        )
        return job.id

    def get_job_status(self, job_id: str, user_id: int) -> JobStatusResponse:
        """Return the status/result of a job, if it belongs to the given user."""
        try:
            job = Job.fetch(job_id, connection=self.queue.connection)
        except NoSuchJobError as exc:
            raise JobNotFoundError(f"No job found with ID '{job_id}'.") from exc

        if job.meta.get("user_id") != user_id:
            raise JobNotFoundError(f"No job found with ID '{job_id}'.")

        return JobStatusResponse(
            job_id=job.id,
            status=job.get_status().value,
            result=job.result,
            error=str(job.exc_info) if job.is_failed else None,
        )
