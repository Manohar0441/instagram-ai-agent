from datetime import datetime, timedelta, timezone

from app.core.settings import settings
from app.integrations.ai_agent import generate_structured_response
from app.schemas.insights import RecommendationNarratives, RecommendationsResponse
from app.services.ai_generation import AIProviderError, ProviderError, build_llm, ensure_configured
from app.services.analytics_service import AnalyticsService
from app.services.insight_prompts import RECOMMENDATIONS_SYSTEM_PROMPT, build_recommendations_user_prompt
from app.utils.analytics_calculations import as_aware_utc
from app.utils.cache import get_or_generate
from app.utils.insight_calculations import content_format_breakdown, posting_frequency, posting_time_breakdown

DEFAULT_RECOMMENDATIONS_LOOKBACK_DAYS = 30
MEDIA_SAMPLE_LIMIT = 50
TOP_CONTENT_SAMPLE_LIMIT = 5


class RecommendationService:
    """Generate personalized content recommendations from stored analytics.

    Posting-time, format, and frequency patterns are computed deterministically
    in code; the LLM is only asked to narrate them and to suggest content
    ideas, grounded in the account's own top-performing posts.
    """

    def __init__(self, analytics_service: AnalyticsService) -> None:
        """Initialize the service with its analytics dependency."""
        self.analytics_service = analytics_service

    def get_recommendations(
        self, user_id: int, days: int = DEFAULT_RECOMMENDATIONS_LOOKBACK_DAYS
    ) -> RecommendationsResponse:
        """Return grounded, personalized recommendations for the given user.

        Results are cached for CACHE_TTL_SECONDS, since each call costs one
        LLM request - repeated calls within the window skip generation.
        """
        cache_key = f"recommendations:{user_id}:{days}"
        return get_or_generate(
            cache_key,
            RecommendationsResponse,
            settings.CACHE_TTL_SECONDS,
            lambda: self._generate_recommendations(user_id, days),
        )

    def _generate_recommendations(self, user_id: int, days: int) -> RecommendationsResponse:
        ensure_configured()

        media = self.analytics_service.get_media_analytics(user_id, limit=MEDIA_SAMPLE_LIMIT)
        top_content = self.analytics_service.get_top_content(
            user_id, limit=TOP_CONTENT_SAMPLE_LIMIT, metric="engagement_rate", order="top"
        )

        since = datetime.now(timezone.utc) - timedelta(days=days)
        recent_media = [
            item for item in media if item.posted_at is not None and as_aware_utc(item.posted_at) >= since
        ]

        context = {
            "period_days": days,
            "posting_time_breakdown": posting_time_breakdown(media),
            "content_format_breakdown": content_format_breakdown(media),
            "posting_frequency": posting_frequency(recent_media, window_days=days),
            "top_performing_content": [item.model_dump(mode="json") for item in top_content.items],
        }

        try:
            narratives = generate_structured_response(
                build_llm(),
                RECOMMENDATIONS_SYSTEM_PROMPT,
                build_recommendations_user_prompt(context),
                RecommendationNarratives,
            )
        except ProviderError as exc:
            raise AIProviderError(f"The AI provider request failed: {exc}") from exc

        return RecommendationsResponse(
            **narratives.model_dump(),
            generated_at=datetime.now(timezone.utc),
        )
