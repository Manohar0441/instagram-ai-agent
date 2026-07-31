from datetime import datetime, timedelta, timezone
from typing import Literal

import openai

from app.core.settings import settings
from app.integrations.ai_agent import generate_structured_response
from app.schemas.insights import PerformanceReportResponse, ReportNarratives
from app.services.ai_generation import AIProviderError, build_llm, ensure_configured
from app.services.analytics_service import AnalyticsService
from app.services.insight_prompts import REPORT_SYSTEM_PROMPT, build_report_user_prompt
from app.utils.cache import get_or_generate

REPORT_CONTENT_LIMIT = 3

# Weekly and monthly reports differ only in lookback window and trend
# granularity - both flow through the same generation logic below.
_PERIOD_CONFIG: dict[str, dict] = {
    "weekly": {"days": 7, "trend_granularity": "daily"},
    "monthly": {"days": 30, "trend_granularity": "weekly"},
}


class ReportService:
    """Generate weekly/monthly AI performance reports from stored analytics.

    Top- and underperforming content lists come directly from
    AnalyticsService (never from the model); the LLM is only asked to write
    the summary and strategic narrative fields (see ReportNarratives).
    """

    def __init__(self, analytics_service: AnalyticsService) -> None:
        """Initialize the service with its analytics dependency."""
        self.analytics_service = analytics_service

    def generate_report(self, user_id: int, period: Literal["weekly", "monthly"]) -> PerformanceReportResponse:
        """Return an AI-generated performance report for the given period.

        Results are cached for CACHE_TTL_SECONDS, since each call costs one
        LLM request - repeated calls within the window skip generation.
        """
        cache_key = f"report:{user_id}:{period}"
        return get_or_generate(
            cache_key,
            PerformanceReportResponse,
            settings.CACHE_TTL_SECONDS,
            lambda: self._generate_report(user_id, period),
        )

    def _generate_report(self, user_id: int, period: Literal["weekly", "monthly"]) -> PerformanceReportResponse:
        ensure_configured()
        config = _PERIOD_CONFIG[period]
        days = config["days"]

        account = self.analytics_service.get_account_analytics(user_id, days=days)
        trends = self.analytics_service.get_trends(
            user_id, granularity=config["trend_granularity"], days=days
        )
        top_content = self.analytics_service.get_top_content(
            user_id, limit=REPORT_CONTENT_LIMIT, metric="engagement_rate", order="top"
        )
        underperforming_content = self.analytics_service.get_top_content(
            user_id, limit=REPORT_CONTENT_LIMIT, metric="engagement_rate", order="bottom"
        )

        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(days=days)).date()
        period_end = now.date()

        context = {
            "period": period,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "account_analytics": account.model_dump(mode="json"),
            "trend_points": [point.model_dump(mode="json") for point in trends.points],
            "top_performing_content": [item.model_dump(mode="json") for item in top_content.items],
            "underperforming_content": [
                item.model_dump(mode="json") for item in underperforming_content.items
            ],
        }

        try:
            narratives = generate_structured_response(
                build_llm(),
                REPORT_SYSTEM_PROMPT,
                build_report_user_prompt(context),
                ReportNarratives,
            )
        except openai.OpenAIError as exc:
            raise AIProviderError(f"The AI provider request failed: {exc}") from exc

        return PerformanceReportResponse(
            period=period,
            period_start=period_start,
            period_end=period_end,
            summary=narratives.summary,
            top_performing_content=top_content.items,
            underperforming_content=underperforming_content.items,
            key_strengths=narratives.key_strengths,
            areas_for_improvement=narratives.areas_for_improvement,
            actionable_next_steps=narratives.actionable_next_steps,
            generated_at=now,
        )
