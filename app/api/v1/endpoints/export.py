from typing import Annotated, cast, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_full_report_export_service
from app.models.user import User
from app.schemas.export import ExportWindowDays, FullReportExportResponse
from app.services.export_service import FullReportExportService
from app.services.instagram_service import InstagramAccountNotConnectedError

router = APIRouter(prefix="/export", tags=["Export"])

CurrentUser = Annotated[User, Depends(get_current_user)]
ExportServiceDependency = Annotated[FullReportExportService, Depends(get_full_report_export_service)]

# Query params always arrive as strings, and pydantic v2's Literal validator
# does not coerce "30" -> 30 the way it does for a plain `int` field - so
# `days` is accepted as an int here and checked against this set by hand,
# rather than typed directly as ExportWindowDays (which would 422 on every
# real request).
_ALLOWED_WINDOW_DAYS = frozenset(get_args(ExportWindowDays))


@router.get(
    "/full-report",
    response_model=FullReportExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the full auditable report bundle",
    description=(
        "Return every analytics section that feeds the AI, plus all three AI outputs "
        "(insights, recommendations, and the period report), for one selectable lookback "
        "window. Any AI section that cannot be generated (quota exhausted, rate limited, "
        "no Gemini key configured, provider outage) comes back with status=\"unavailable\" "
        "and a machine-readable reason instead of failing the request - the rest of the "
        "bundle, including every input the AI would have seen, still returns 200."
    ),
    operation_id="getFullReportExport",
    responses={
        status.HTTP_200_OK: {
            "description": "Bundle returned. Individual AI sections may still be unavailable."
        },
        status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Export rate limit exceeded."},
    },
)
@limiter.limit(settings.RATE_LIMIT_EXPORT)
def get_full_report_export(
    request: Request,
    current_user: CurrentUser,
    export_service: ExportServiceDependency,
    days: Annotated[int, Query(description="Lookback window in days.")] = 30,
) -> FullReportExportResponse:
    """Return the full auditable report bundle for the current user."""
    if days not in _ALLOWED_WINDOW_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"days must be one of {sorted(_ALLOWED_WINDOW_DAYS)}",
        )
    try:
        return export_service.generate_export(current_user.id, days=cast(ExportWindowDays, days))
    except InstagramAccountNotConnectedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
