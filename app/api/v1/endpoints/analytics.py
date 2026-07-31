from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_analytics_service
from app.models.user import User
from app.schemas.analytics import (
    AccountAnalyticsResponse,
    DashboardResponse,
    MediaAnalyticsResponse,
    TopContentResponse,
    TrendsResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.instagram_service import InstagramAccountNotConnectedError

router = APIRouter(prefix="/analytics", tags=["Analytics"])

AnalyticsServiceDependency = Annotated[AnalyticsService, Depends(get_analytics_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]

NOT_CONNECTED_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."}
}


def _not_connected(exc: InstagramAccountNotConnectedError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/account",
    response_model=AccountAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get account analytics",
    description="Return account-level analytics (reach, impressions, follower growth, engagement rate) computed from already-fetched Instagram data.",
    operation_id="getAccountAnalytics",
    responses={
        status.HTTP_200_OK: {"description": "Account analytics returned successfully."},
        **NOT_CONNECTED_RESPONSE,
    },
)
def get_account_analytics(
    current_user: CurrentUser,
    analytics_service: AnalyticsServiceDependency,
    days: Annotated[int, Query(gt=0, le=365, description="Lookback window in days.")] = 30,
) -> AccountAnalyticsResponse:
    """Return account-level analytics for the current user."""
    try:
        return analytics_service.get_account_analytics(current_user.id, days=days)
    except InstagramAccountNotConnectedError as exc:
        raise _not_connected(exc) from exc


@router.get(
    "/media",
    response_model=list[MediaAnalyticsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get media analytics",
    description="Return per-post/reel analytics (likes, comments, reach, engagement rate) computed from already-fetched Instagram data.",
    operation_id="getMediaAnalytics",
    responses={
        status.HTTP_200_OK: {"description": "Media analytics returned successfully."},
        **NOT_CONNECTED_RESPONSE,
    },
)
def get_media_analytics(
    current_user: CurrentUser,
    analytics_service: AnalyticsServiceDependency,
    limit: Annotated[int, Query(gt=0, le=100)] = 25,
    media_type: Annotated[str | None, Query(description="Filter by media type, e.g. IMAGE, VIDEO, REELS.")] = None,
) -> list[MediaAnalyticsResponse]:
    """Return per-media analytics for the current user."""
    try:
        return analytics_service.get_media_analytics(current_user.id, limit=limit, media_type=media_type)
    except InstagramAccountNotConnectedError as exc:
        raise _not_connected(exc) from exc


@router.get(
    "/trends",
    response_model=TrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get performance trends",
    description="Return historical performance bucketed by day, week, or month.",
    operation_id="getAnalyticsTrends",
    responses={
        status.HTTP_200_OK: {"description": "Trends returned successfully."},
        **NOT_CONNECTED_RESPONSE,
    },
)
def get_trends(
    current_user: CurrentUser,
    analytics_service: AnalyticsServiceDependency,
    granularity: Annotated[Literal["daily", "weekly", "monthly"], Query()] = "daily",
    days: Annotated[int, Query(gt=0, le=365, description="Lookback window in days.")] = 30,
) -> TrendsResponse:
    """Return historical performance trends for the current user."""
    try:
        return analytics_service.get_trends(current_user.id, granularity=granularity, days=days)
    except InstagramAccountNotConnectedError as exc:
        raise _not_connected(exc) from exc


@router.get(
    "/top-content",
    response_model=TopContentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get top or lowest performing content",
    description="Return content ranked by a chosen metric, best (order=top) or worst (order=bottom) performing first.",
    operation_id="getTopContent",
    responses={
        status.HTTP_200_OK: {"description": "Ranked content returned successfully."},
        **NOT_CONNECTED_RESPONSE,
    },
)
def get_top_content(
    current_user: CurrentUser,
    analytics_service: AnalyticsServiceDependency,
    limit: Annotated[int, Query(gt=0, le=50)] = 5,
    metric: Annotated[
        Literal["engagement_rate", "reach", "likes", "comments", "impressions"], Query()
    ] = "engagement_rate",
    order: Annotated[Literal["top", "bottom"], Query()] = "top",
) -> TopContentResponse:
    """Return content ranked by the chosen performance metric."""
    try:
        return analytics_service.get_top_content(current_user.id, limit=limit, metric=metric, order=order)
    except InstagramAccountNotConnectedError as exc:
        raise _not_connected(exc) from exc


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Get dashboard summary",
    description="Return a summarized dashboard combining account analytics, top content, and a recent trend snapshot.",
    operation_id="getAnalyticsDashboard",
    responses={
        status.HTTP_200_OK: {"description": "Dashboard summary returned successfully."},
        **NOT_CONNECTED_RESPONSE,
    },
)
def get_dashboard(
    current_user: CurrentUser,
    analytics_service: AnalyticsServiceDependency,
) -> DashboardResponse:
    """Return a summarized analytics dashboard for the current user."""
    try:
        return analytics_service.get_dashboard(current_user.id)
    except InstagramAccountNotConnectedError as exc:
        raise _not_connected(exc) from exc
