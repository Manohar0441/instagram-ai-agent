from datetime import datetime, timezone

from app.core.settings import settings
from app.integrations.ai_agent import generate_structured_response
from app.schemas.insights import RecommendationNarratives, RecommendationsResponse
from app.services.ai_context import build_recommendations_context
from app.services.ai_credential_service import AICredentialService
from app.services.ai_generation import ProviderError, build_llm, wrap_provider_error
from app.services.analytics_service import AnalyticsService
from app.services.insight_prompts import RECOMMENDATIONS_SYSTEM_PROMPT, build_recommendations_user_prompt
from app.utils.cache import get_or_generate

DEFAULT_RECOMMENDATIONS_LOOKBACK_DAYS = 30


class RecommendationService:
    """Generate personalized content recommendations from stored analytics.

    Posting-time, format, and frequency patterns are computed deterministically
    in code; the LLM is only asked to narrate them and to suggest content
    ideas, grounded in the account's own top-performing posts.
    """

    def __init__(
        self,
        analytics_service: AnalyticsService,
        credential_service: AICredentialService,
    ) -> None:
        """Initialize the service with its analytics and credential dependencies."""
        self.analytics_service = analytics_service
        self.credential_service = credential_service

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
        api_key = self.credential_service.resolve_api_key(user_id)
        ctx = build_recommendations_context(self.analytics_service, user_id, days)

        try:
            narratives = generate_structured_response(
                build_llm(api_key),
                RECOMMENDATIONS_SYSTEM_PROMPT,
                build_recommendations_user_prompt(ctx.prompt_context),
                RecommendationNarratives,
            )
        except ProviderError as exc:
            raise wrap_provider_error(exc) from exc

        return RecommendationsResponse(
            **narratives.model_dump(),
            generated_at=datetime.now(timezone.utc),
        )
