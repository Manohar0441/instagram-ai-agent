from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.analytics import (
    AccountAnalyticsResponse,
    MediaAnalyticsResponse,
    TopContentResponse,
    TrendsResponse,
)
from app.schemas.insights import (
    PerformanceInsightsResponse,
    PerformanceReportResponse,
    RecommendationsResponse,
)

# A closed set rather than a free integer. The AI layer's own cache keys are
# insights:{user_id}:{days} / recommendations:{user_id}:{days} - an open
# range would mean up to 365 distinct cache entries per user, and every
# distinct value costs a fresh set of Gemini calls the first time it's
# requested. Six values bounds that exposure and is what a window selector
# in the UI wants anyway.
ExportWindowDays = Literal[7, 14, 30, 90, 180, 365]

Granularity = Literal["daily", "weekly", "monthly"]

AIFailureReason = Literal[
    "not_configured",
    "rate_limited",
    "provider_error",
    "generation_error",
    "unexpected_error",
]


class AIFailure(BaseModel):
    """Why one AI section of the export could not be generated."""

    reason: AIFailureReason
    message: str
    retriable: bool


class ContentSummary(BaseModel):
    """Aggregate post count, average engagement, and totals across a sample."""

    post_count: int
    average_engagement_rate: float | None = None
    total_likes: int | None = None
    total_comments: int | None = None


class SampleProvenance(BaseModel):
    """How a media sample used for a breakdown was selected."""

    limit: int
    returned: int
    window_filtered: bool


class InsightsInputs(BaseModel):
    """Exactly what InsightsService sends to the model - the audit record
    for the insights section. Computed by the same code path the AI
    service itself calls (see app/services/ai_context.py), so it can never
    drift from what the model actually saw."""

    period_days: int
    account_analytics: AccountAnalyticsResponse
    content_summary: ContentSummary
    trend_points: list[dict[str, Any]]
    trend_granularity: Granularity
    posting_time_breakdown: dict[str, Any]
    sample: SampleProvenance


class RecommendationsInputs(BaseModel):
    """Exactly what RecommendationService sends to the model."""

    period_days: int
    posting_time_breakdown: dict[str, Any]
    content_format_breakdown: dict[str, Any]
    posting_frequency: dict[str, Any]
    top_performing_content: list[MediaAnalyticsResponse]
    sample: SampleProvenance
    recent_sample_size: int


class ReportInputs(BaseModel):
    """Exactly what ReportService sends to the model."""

    period: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    account_analytics: AccountAnalyticsResponse
    trend_points: list[dict[str, Any]]
    trend_granularity: Granularity
    top_performing_content: list[MediaAnalyticsResponse]
    underperforming_content: list[MediaAnalyticsResponse]
    content_limit: int


class InsightsSection(BaseModel):
    """The insights AI artifact, or why it's unavailable - inputs are
    always present since they come from our own analytics code, not the
    model, so they survive an AI outage."""

    status: Literal["ok", "unavailable"]
    data: PerformanceInsightsResponse | None
    failure: AIFailure | None
    served_from_cache: bool
    inputs: InsightsInputs


class RecommendationsSection(BaseModel):
    status: Literal["ok", "unavailable"]
    data: RecommendationsResponse | None
    failure: AIFailure | None
    served_from_cache: bool
    inputs: RecommendationsInputs


class ReportSection(BaseModel):
    status: Literal["ok", "unavailable"]
    data: PerformanceReportResponse | None
    failure: AIFailure | None
    served_from_cache: bool
    inputs: ReportInputs
    period_label: Literal["weekly", "monthly"]
    period_days: int
    covers_export_window: bool


class WindowBreakdowns(BaseModel):
    """Posting-time, format, and frequency breakdowns computed over only
    the posts published inside the selected window - what the user would
    expect "my last N days" to mean, as opposed to InsightsInputs /
    RecommendationsInputs' unfiltered AI sample (see BreakdownDivergence)."""

    posting_time: dict[str, Any]
    content_format: dict[str, Any]
    posting_frequency: dict[str, Any]
    content_summary: ContentSummary
    sample: SampleProvenance


class ContentInventory(BaseModel):
    """Every post published inside the window, up to a page-count-friendly cap."""

    items: list[MediaAnalyticsResponse]
    total_in_window: int
    truncated: bool
    limit: int
    excluded_undated_count: int


class WindowAnalytics(BaseModel):
    account: AccountAnalyticsResponse
    trends: TrendsResponse
    inventory: ContentInventory
    top_content: TopContentResponse
    bottom_content: TopContentResponse
    breakdowns: WindowBreakdowns


class BreakdownDivergence(BaseModel):
    """Whether the AI's unwindowed sample and the window-filtered analytics
    actually cover the same posts - the finding this export exists to
    surface. When they differ, the AI's narrative may be describing a
    materially different set of posts than the window the user selected."""

    ai_sample_size: int
    window_sample_size: int
    differs: bool
    explanation: str


class Methodology(BaseModel):
    """Documents which inputs, sample sizes, and parameters produced each
    section, so the bundle can be audited rather than taken on faith."""

    granularity_rule: str
    report_period_rule: str
    breakdown_divergence: BreakdownDivergence
    media_sample_limit: int
    inventory_limit: int
    ranked_content_limit: int
    timezone: Literal["UTC"]
    cache_ttl_seconds: int


class ExportMeta(BaseModel):
    schema_version: Literal[1] = 1
    generated_at: datetime
    days: ExportWindowDays
    window_start: date
    window_end: date
    username: str
    instagram_user_id: str
    ai_sections_ok: int
    ai_sections_total: Literal[3] = 3


class FullReportExportResponse(BaseModel):
    """The full auditable report bundle: every analytics section that feeds
    the AI, plus all three AI outputs, for one selectable window."""

    meta: ExportMeta
    methodology: Methodology
    analytics: WindowAnalytics
    insights: InsightsSection
    recommendations: RecommendationsSection
    report: ReportSection
