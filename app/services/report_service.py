from typing import Literal

from app.core.settings import settings
from app.integrations.ai_agent import generate_structured_response
from app.schemas.insights import PerformanceReportResponse, ReportNarratives
from app.services.ai_context import build_report_context
from app.services.ai_credential_service import AICredentialService
from app.services.ai_generation import ProviderError, build_llm, wrap_provider_error
from app.services.analytics_service import AnalyticsService
from app.services.insight_prompts import REPORT_SYSTEM_PROMPT, build_report_user_prompt
from app.utils.cache import get_or_generate


class ReportService:
    """Generate weekly/monthly AI performance reports from stored analytics.

    Top- and underperforming content lists come directly from
    AnalyticsService (never from the model); the LLM is only asked to write
    the summary and strategic narrative fields (see ReportNarratives).
    """

    def __init__(
        self,
        analytics_service: AnalyticsService,
        credential_service: AICredentialService,
    ) -> None:
        """Initialize the service with its analytics and credential dependencies."""
        self.analytics_service = analytics_service
        self.credential_service = credential_service

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
        api_key = self.credential_service.resolve_api_key(user_id)
        ctx = build_report_context(self.analytics_service, user_id, period)

        try:
            narratives = generate_structured_response(
                build_llm(api_key),
                REPORT_SYSTEM_PROMPT,
                build_report_user_prompt(ctx.prompt_context),
                ReportNarratives,
            )
        except ProviderError as exc:
            raise wrap_provider_error(exc) from exc

        return PerformanceReportResponse(
            period=period,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            summary=narratives.summary,
            top_performing_content=ctx.top_content.items,
            underperforming_content=ctx.underperforming_content.items,
            key_strengths=narratives.key_strengths,
            areas_for_improvement=narratives.areas_for_improvement,
            actionable_next_steps=narratives.actionable_next_steps,
            generated_at=ctx.now,
        )
