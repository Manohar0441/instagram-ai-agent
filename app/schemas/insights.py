from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.analytics import MediaAnalyticsResponse

# --- Public API response schemas -------------------------------------------


class Insight(BaseModel):
    """A single grounded insight: an LLM-written narrative plus the real
    analytics data it was asked to base that narrative on."""

    title: str
    summary: str
    supporting_data: dict[str, Any]


class PerformanceInsightsResponse(BaseModel):
    """AI-generated performance insights across account, content, and growth."""

    account_performance: Insight
    content_performance: Insight
    growth_trend: Insight
    engagement_trend: Insight
    audience_behavior: Insight
    generated_at: datetime


class RecommendationsResponse(BaseModel):
    """Personalized, data-grounded content recommendations."""

    best_posting_times: str
    recommended_content_formats: str
    content_ideas: list[str]
    posting_frequency: str
    engagement_reach_tips: list[str]
    generated_at: datetime


class PerformanceReportResponse(BaseModel):
    """A weekly or monthly AI-generated performance report."""

    period: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    summary: str
    top_performing_content: list[MediaAnalyticsResponse]
    underperforming_content: list[MediaAnalyticsResponse]
    key_strengths: list[str]
    areas_for_improvement: list[str]
    actionable_next_steps: list[str]
    generated_at: datetime


# --- Internal: shapes the LLM is asked to produce via structured output.
#
# These are intentionally narrower than the response schemas above - they
# hold only the fields the LLM should actually generate (narrative text).
# Fields like generated_at, supporting_data, and top/underperforming content
# are never asked of the LLM; the service layer attaches those itself from
# real AnalyticsService data, so a hallucinated or stale narrative can never
# corrupt the numbers a client sees.


class InsightNarratives(BaseModel):
    """LLM-generated narrative text for each performance insight category."""

    account_performance: str
    content_performance: str
    growth_trend: str
    engagement_trend: str
    audience_behavior: str


class RecommendationNarratives(BaseModel):
    """LLM-generated recommendation text (equivalent to RecommendationsResponse minus generated_at)."""

    best_posting_times: str
    recommended_content_formats: str
    content_ideas: list[str]
    posting_frequency: str
    engagement_reach_tips: list[str]


class ReportNarratives(BaseModel):
    """LLM-generated narrative portions of a performance report."""

    summary: str
    key_strengths: list[str]
    areas_for_improvement: list[str]
    actionable_next_steps: list[str]
