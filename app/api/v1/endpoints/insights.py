from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import (
    get_insights_service,
    get_recommendation_service,
    get_report_service,
)
from app.models.user import User
from app.schemas.insights import (
    PerformanceInsightsResponse,
    PerformanceReportResponse,
    RecommendationsResponse,
)
from app.services.ai_generation import AIGenerationError, AINotConfiguredError, AIProviderError
from app.services.insights_service import InsightsService
from app.services.instagram_service import InstagramAccountNotConnectedError
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService

router = APIRouter(tags=["AI Insights"])

CurrentUser = Annotated[User, Depends(get_current_user)]
InsightsServiceDependency = Annotated[InsightsService, Depends(get_insights_service)]
RecommendationServiceDependency = Annotated[RecommendationService, Depends(get_recommendation_service)]
ReportServiceDependency = Annotated[ReportService, Depends(get_report_service)]

_COMMON_RESPONSES = {
    status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
    status.HTTP_502_BAD_GATEWAY: {"description": "The AI provider request failed."},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The AI service is not configured."},
}


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InstagramAccountNotConnectedError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, AINotConfiguredError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, AIProviderError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/insights",
    response_model=PerformanceInsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get AI performance insights",
    description="Return AI-generated performance insights (account, content, growth, engagement, audience behavior), grounded in the current user's stored analytics.",
    operation_id="getPerformanceInsights",
    responses={status.HTTP_200_OK: {"description": "Insights returned successfully."}, **_COMMON_RESPONSES},
)
def get_insights(
    current_user: CurrentUser,
    insights_service: InsightsServiceDependency,
) -> PerformanceInsightsResponse:
    """Return AI-generated performance insights for the current user."""
    try:
        return insights_service.get_insights(current_user.id)
    except (InstagramAccountNotConnectedError, AIGenerationError) as exc:
        raise _handle_error(exc) from exc


@router.get(
    "/recommendations",
    response_model=RecommendationsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get personalized recommendations",
    description="Return personalized, data-grounded content recommendations for the current user.",
    operation_id="getRecommendations",
    responses={status.HTTP_200_OK: {"description": "Recommendations returned successfully."}, **_COMMON_RESPONSES},
)
def get_recommendations(
    current_user: CurrentUser,
    recommendation_service: RecommendationServiceDependency,
) -> RecommendationsResponse:
    """Return AI-generated recommendations for the current user."""
    try:
        return recommendation_service.get_recommendations(current_user.id)
    except (InstagramAccountNotConnectedError, AIGenerationError) as exc:
        raise _handle_error(exc) from exc


def _generate_report(
    period: Literal["weekly", "monthly"],
    current_user: User,
    report_service: ReportService,
) -> PerformanceReportResponse:
    try:
        return report_service.generate_report(current_user.id, period=period)
    except (InstagramAccountNotConnectedError, AIGenerationError) as exc:
        raise _handle_error(exc) from exc


@router.get(
    "/reports/weekly",
    response_model=PerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get weekly AI report",
    description="Generate a weekly AI performance report for the current user.",
    operation_id="getWeeklyReport",
    responses={status.HTTP_200_OK: {"description": "Weekly report returned successfully."}, **_COMMON_RESPONSES},
)
def get_weekly_report(
    current_user: CurrentUser,
    report_service: ReportServiceDependency,
) -> PerformanceReportResponse:
    """Return a weekly AI-generated performance report for the current user."""
    return _generate_report("weekly", current_user, report_service)


@router.get(
    "/reports/monthly",
    response_model=PerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get monthly AI report",
    description="Generate a monthly AI performance report for the current user.",
    operation_id="getMonthlyReport",
    responses={status.HTTP_200_OK: {"description": "Monthly report returned successfully."}, **_COMMON_RESPONSES},
)
def get_monthly_report(
    current_user: CurrentUser,
    report_service: ReportServiceDependency,
) -> PerformanceReportResponse:
    """Return a monthly AI-generated performance report for the current user."""
    return _generate_report("monthly", current_user, report_service)
