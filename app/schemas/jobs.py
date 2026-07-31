from typing import Any, Literal

from pydantic import BaseModel


class JobEnqueuedResponse(BaseModel):
    """Returned immediately after a background job is queued."""

    job_id: str
    status: Literal["queued"] = "queued"


class JobStatusResponse(BaseModel):
    """The current status (and result, once finished) of a background job."""

    job_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
