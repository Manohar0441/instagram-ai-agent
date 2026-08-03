"""Build the exact data each AI service sends to Gemini.

Extracted out of InsightsService/RecommendationService/ReportService so that
"what the AI actually saw" has exactly one implementation. The full-report
export (app/services/export_service.py) calls the same builders the AI
services call - if it re-derived this itself instead, the two would drift
the first time someone changed a sample limit or a lookback window, and the
export's whole purpose is to be a trustworthy audit trail.

Each builder returns a small dataclass carrying:
  - `inputs`: a typed, Pydantic record of what was gathered (for the export).
  - the raw pieces the AI service's response assembly still needs (e.g. the
    ranked content lists, so it can attach them to the response verbatim).
  - `prompt_context`: the exact dict handed to the prompt builder + LLM -
    byte-identical to what each service constructed before this refactor.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from app.schemas.analytics import AccountAnalyticsResponse, TopContentResponse, TrendsResponse
from app.schemas.export import (
    ContentSummary,
    InsightsInputs,
    RecommendationsInputs,
    ReportInputs,
    SampleProvenance,
)
from app.services.analytics_service import AnalyticsService
from app.utils.analytics_calculations import published_within, with_ist_posted_at
from app.utils.insight_calculations import content_format_breakdown, content_summary, posting_frequency, posting_time_breakdown

MEDIA_SAMPLE_LIMIT = 50
TOP_CONTENT_SAMPLE_LIMIT = 5
REPORT_CONTENT_LIMIT = 3

# Weekly and monthly reports differ only in lookback window and trend
# granularity - both flow through the same generation logic.
PERIOD_CONFIG: dict[str, dict[str, Any]] = {
    "weekly": {"days": 7, "trend_granularity": "daily"},
    "monthly": {"days": 30, "trend_granularity": "weekly"},
}


@dataclass
class InsightsContext:
    inputs: InsightsInputs
    account: AccountAnalyticsResponse
    posting_time_breakdown: dict[str, Any]
    content_summary: dict[str, Any]
    prompt_context: dict[str, Any]


@dataclass
class RecommendationsContext:
    inputs: RecommendationsInputs
    prompt_context: dict[str, Any]


@dataclass
class ReportContext:
    inputs: ReportInputs
    top_content: TopContentResponse
    underperforming_content: TopContentResponse
    period_start: Any  # date
    period_end: Any  # date
    now: datetime
    prompt_context: dict[str, Any]


def build_insights_context(
    analytics_service: AnalyticsService, user_id: int, days: int
) -> InsightsContext:
    account = analytics_service.get_account_analytics(user_id, days=days)
    media = analytics_service.get_media_analytics(user_id, limit=MEDIA_SAMPLE_LIMIT)
    trends = analytics_service.get_trends(user_id, granularity="daily", days=days)
    timing = posting_time_breakdown(media)
    summary_dict = content_summary(media)
    trend_dump = [point.model_dump(mode="json") for point in trends.points]

    prompt_context = {
        "period_days": days,
        "account_analytics": account.model_dump(mode="json"),
        "content_summary": summary_dict,
        "trend_points": trend_dump,
        "posting_time_breakdown": timing,
    }

    inputs = InsightsInputs(
        period_days=days,
        account_analytics=account,
        content_summary=ContentSummary(**summary_dict),
        trend_points=trend_dump,
        trend_granularity="daily",
        posting_time_breakdown=timing,
        sample=SampleProvenance(limit=MEDIA_SAMPLE_LIMIT, returned=len(media), window_filtered=False),
    )

    return InsightsContext(
        inputs=inputs,
        account=account,
        posting_time_breakdown=timing,
        content_summary=summary_dict,
        prompt_context=prompt_context,
    )


def build_recommendations_context(
    analytics_service: AnalyticsService, user_id: int, days: int
) -> RecommendationsContext:
    media = analytics_service.get_media_analytics(user_id, limit=MEDIA_SAMPLE_LIMIT)
    top_content = analytics_service.get_top_content(
        user_id, limit=TOP_CONTENT_SAMPLE_LIMIT, metric="engagement_rate", order="top"
    )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    recent_media = published_within(media, since)

    # posted_at is UTC (storage/Graph API timezone); shifted to IST before
    # it reaches the prompt or the export audit trail below, so both agree
    # with what a person reading a clock time would expect.
    top_content_items = [with_ist_posted_at(item) for item in top_content.items]

    timing = posting_time_breakdown(media)
    formats = content_format_breakdown(media)
    frequency = posting_frequency(recent_media, window_days=days)
    top_dump = [item.model_dump(mode="json") for item in top_content_items]

    prompt_context = {
        "period_days": days,
        "posting_time_breakdown": timing,
        "content_format_breakdown": formats,
        "posting_frequency": frequency,
        "top_performing_content": top_dump,
    }

    inputs = RecommendationsInputs(
        period_days=days,
        posting_time_breakdown=timing,
        content_format_breakdown=formats,
        posting_frequency=frequency,
        top_performing_content=top_content_items,
        sample=SampleProvenance(limit=MEDIA_SAMPLE_LIMIT, returned=len(media), window_filtered=False),
        recent_sample_size=len(recent_media),
    )

    return RecommendationsContext(inputs=inputs, prompt_context=prompt_context)


def build_report_context(
    analytics_service: AnalyticsService, user_id: int, period: Literal["weekly", "monthly"]
) -> ReportContext:
    config = PERIOD_CONFIG[period]
    days = config["days"]
    trend_granularity = config["trend_granularity"]

    account = analytics_service.get_account_analytics(user_id, days=days)
    trends: TrendsResponse = analytics_service.get_trends(
        user_id, granularity=trend_granularity, days=days
    )
    top_content = analytics_service.get_top_content(
        user_id, limit=REPORT_CONTENT_LIMIT, metric="engagement_rate", order="top"
    )
    underperforming_content = analytics_service.get_top_content(
        user_id, limit=REPORT_CONTENT_LIMIT, metric="engagement_rate", order="bottom"
    )

    now = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=days)).date()
    period_end = now.date()

    # posted_at is UTC (storage/Graph API timezone); shifted to IST so the
    # prompt, the export audit trail, and the report response actually
    # shown to the user (report_service.py reads ctx.top_content /
    # ctx.underperforming_content directly) all agree on the same time.
    top_content = top_content.model_copy(
        update={"items": [with_ist_posted_at(item) for item in top_content.items]}
    )
    underperforming_content = underperforming_content.model_copy(
        update={"items": [with_ist_posted_at(item) for item in underperforming_content.items]}
    )

    trend_dump = [point.model_dump(mode="json") for point in trends.points]
    top_dump = [item.model_dump(mode="json") for item in top_content.items]
    under_dump = [item.model_dump(mode="json") for item in underperforming_content.items]

    prompt_context = {
        "period": period,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "account_analytics": account.model_dump(mode="json"),
        "trend_points": trend_dump,
        "top_performing_content": top_dump,
        "underperforming_content": under_dump,
    }

    inputs = ReportInputs(
        period=period,
        period_start=period_start,
        period_end=period_end,
        account_analytics=account,
        trend_points=trend_dump,
        trend_granularity=trend_granularity,
        top_performing_content=top_content.items,
        underperforming_content=underperforming_content.items,
        content_limit=REPORT_CONTENT_LIMIT,
    )

    return ReportContext(
        inputs=inputs,
        top_content=top_content,
        underperforming_content=underperforming_content,
        period_start=period_start,
        period_end=period_end,
        now=now,
        prompt_context=prompt_context,
    )
