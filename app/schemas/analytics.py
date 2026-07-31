from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class GrowthMetric(BaseModel):
    """Absolute and percentage change between two point-in-time values."""

    absolute: int
    percentage: float | None


class AccountAnalyticsResponse(BaseModel):
    """Account-level analytics for the connected Instagram account."""

    instagram_user_id: str
    username: str
    followers_count: int | None
    follower_growth: GrowthMetric | None
    media_count: int | None
    reach: int | None
    impressions: int | None
    profile_visits: int | None
    accounts_reached: int | None
    accounts_engaged: int | None
    engagement_rate: float | None
    period_days: int
    last_updated: datetime | None


class MediaAnalyticsResponse(BaseModel):
    """Analytics for a single post or reel."""

    media_id: str
    media_type: str
    caption: str | None
    permalink: str | None
    posted_at: datetime | None
    likes: int | None
    comments: int | None
    shares: int | None
    saves: int | None
    reach: int | None
    impressions: int | None
    engagement_rate: float | None
    watch_time: int | None
    completion_rate: float | None
    insights_fetched_at: datetime | None


class TrendPoint(BaseModel):
    """Aggregated metrics for a single time bucket in a trend series."""

    period_start: date
    reach: int | None
    impressions: int | None
    profile_visits: int | None
    followers_count: int | None
    posts_count: int
    average_engagement_rate: float | None


class TrendsResponse(BaseModel):
    """Historical performance trends bucketed by granularity."""

    granularity: Literal["daily", "weekly", "monthly"]
    points: list[TrendPoint]


class TopContentResponse(BaseModel):
    """Content ranked by a chosen performance metric."""

    metric: str
    order: Literal["top", "bottom"]
    items: list[MediaAnalyticsResponse]


class DashboardResponse(BaseModel):
    """Summarized dashboard combining account, content, and trend data."""

    account: AccountAnalyticsResponse
    top_content: list[MediaAnalyticsResponse]
    recent_trend: list[TrendPoint]
