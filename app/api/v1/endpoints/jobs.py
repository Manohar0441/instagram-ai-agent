from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_job_service
from app.models.user import User
from app.schemas.jobs import JobEnqueuedResponse, JobStatusResponse
from app.services.job_service import JobNotFoundError, JobService

router = APIRouter(prefix="/jobs", tags=["Background Jobs"])

CurrentUser = Annotated[User, Depends(get_current_user)]
JobServiceDependency = Annotated[JobService, Depends(get_job_service)]


@router.post(
    "/reports/{period}",
    response_model=JobEnqueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a report generation job",
    description="Queue weekly/monthly AI report generation as a background job. Poll GET /jobs/{job_id} for the result.",
    operation_id="enqueueReportGeneration",
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Job queued successfully."},
    },
)
@limiter.limit(settings.RATE_LIMIT_STRICT)
def enqueue_report(
    request: Request,
    period: Literal["weekly", "monthly"],
    current_user: CurrentUser,
    job_service: JobServiceDependency,
) -> JobEnqueuedResponse:
    """Queue background generation of a report for the current user."""
    job_id = job_service.enqueue_report_generation(current_user.id, period)
    return JobEnqueuedResponse(job_id=job_id)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get background job status",
    description="Return the status (and result, once finished) of a background job belonging to the current user.",
    operation_id="getJobStatus",
    responses={
        status.HTTP_200_OK: {"description": "Job status returned successfully."},
        status.HTTP_404_NOT_FOUND: {"description": "No job with this ID exists for the current user."},
    },
)
def get_job(
    job_id: str,
    current_user: CurrentUser,
    job_service: JobServiceDependency,
) -> JobStatusResponse:
    """Return the status of a background job, if it belongs to the current user."""
    try:
        return job_service.get_job_status(job_id, current_user.id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
