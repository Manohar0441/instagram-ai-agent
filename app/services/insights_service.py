from datetime import datetime, timezone
from typing import Any

import openai

from app.integrations.ai_agent import generate_structured_response
from app.schemas.analytics import MediaAnalyticsResponse
from app.schemas.insights import Insight, InsightNarratives, PerformanceInsightsResponse
from app.services.ai_generation import AIProviderError, build_llm, ensure_configured
from app.services.analytics_service import AnalyticsService
from app.services.insight_prompts import INSIGHTS_SYSTEM_PROMPT, build_insights_user_prompt
from app.utils.insight_calculations import posting_time_breakdown

DEFAULT_INSIGHTS_LOOKBACK_DAYS = 30
MEDIA_SAMPLE_LIMIT = 50


class InsightsService:
    """Generate AI performance insights grounded in stored analytics data.

    Only ever reads through AnalyticsService, never a repository. The LLM
    is asked to produce narrative text only (see InsightNarratives) - the
    numbers attached to each Insight's supporting_data always come directly
    from AnalyticsService, never from the model.
    """

    def __init__(self, analytics_service: AnalyticsService) -> None:
        """Initialize the service with its analytics dependency."""
        self.analytics_service = analytics_service

    def get_insights(
        self, user_id: int, days: int = DEFAULT_INSIGHTS_LOOKBACK_DAYS
    ) -> PerformanceInsightsResponse:
        """Return five grounded performance insights for the given user."""
        ensure_configured()

        account = self.analytics_service.get_account_analytics(user_id, days=days)
        media = self.analytics_service.get_media_analytics(user_id, limit=MEDIA_SAMPLE_LIMIT)
        trends = self.analytics_service.get_trends(user_id, granularity="daily", days=days)
        timing = posting_time_breakdown(media)
        content_summary = self._content_summary(media)

        context = {
            "period_days": days,
            "account_analytics": account.model_dump(mode="json"),
            "content_summary": content_summary,
            "trend_points": [point.model_dump(mode="json") for point in trends.points],
            "posting_time_breakdown": timing,
        }

        try:
            narratives = generate_structured_response(
                build_llm(),
                INSIGHTS_SYSTEM_PROMPT,
                build_insights_user_prompt(context),
                InsightNarratives,
            )
        except openai.OpenAIError as exc:
            raise AIProviderError(f"The AI provider request failed: {exc}") from exc

        follower_growth = account.follower_growth.model_dump(mode="json") if account.follower_growth else None

        return PerformanceInsightsResponse(
            account_performance=Insight(
                title="Account Performance",
                summary=narratives.account_performance,
                supporting_data=account.model_dump(mode="json"),
            ),
            content_performance=Insight(
                title="Content Performance",
                summary=narratives.content_performance,
                supporting_data=content_summary,
            ),
            growth_trend=Insight(
                title="Growth Trend",
                summary=narratives.growth_trend,
                supporting_data={"follower_growth": follower_growth},
            ),
            engagement_trend=Insight(
                title="Engagement Trend",
                summary=narratives.engagement_trend,
                supporting_data={"trend_points": context["trend_points"]},
            ),
            audience_behavior=Insight(
                title="Audience Behavior",
                summary=narratives.audience_behavior,
                supporting_data=timing,
            ),
            generated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _content_summary(media: list[MediaAnalyticsResponse]) -> dict[str, Any]:
        if not media:
            return {"post_count": 0}

        rates = [item.engagement_rate for item in media if item.engagement_rate is not None]
        return {
            "post_count": len(media),
            "average_engagement_rate": round(sum(rates) / len(rates), 2) if rates else None,
            "total_likes": sum(item.likes or 0 for item in media),
            "total_comments": sum(item.comments or 0 for item in media),
        }
