import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal, TypeVar

from pydantic import BaseModel

from app.core.settings import settings
from app.schemas.export import (
    AIFailure,
    BreakdownDivergence,
    ExportMeta,
    ExportWindowDays,
    FullReportExportResponse,
    Granularity,
    InsightsSection,
    Methodology,
    RecommendationsSection,
    ReportSection,
)
from app.schemas.insights import PerformanceInsightsResponse, PerformanceReportResponse, RecommendationsResponse
from app.services.ai_context import (
    MEDIA_SAMPLE_LIMIT,
    PERIOD_CONFIG,
    build_insights_context,
    build_recommendations_context,
    build_report_context,
)
from app.services.ai_generation import (
    AIGenerationError,
    AINotConfiguredError,
    AIProviderError,
    AIRateLimitedError,
)
from app.services.analytics_service import AnalyticsService
from app.services.insights_service import InsightsService
from app.services.instagram_service import InstagramAccountNotConnectedError
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService
from app.utils.cache import cache_get

logger = logging.getLogger(__name__)

RANKED_CONTENT_LIMIT = 5
INVENTORY_LIMIT = 500

_GENERIC_AI_FAILURE_MESSAGE = "This section could not be generated. Please try the export again."
_GRANULARITY_RULE = "days<=14: daily; days<=90: weekly; else monthly."
_REPORT_PERIOD_RULE = "days<=7: weekly report (7-day lookback); else monthly report (30-day lookback)."
_BREAKDOWN_DIVERGENCE_EXPLANATION = (
    "The AI's posting-time, format, and frequency breakdowns are computed over the most "
    "recent posts with no date filter, so they may cover a longer span than the window "
    "you selected. The window breakdowns above cover only posts published inside it."
)

T = TypeVar("T", bound=BaseModel)


@dataclass
class _AIResult:
    status: Literal["ok", "unavailable"]
    data: BaseModel | None
    failure: AIFailure | None
    served_from_cache: bool


def _granularity_for(days: int) -> Granularity:
    """Pick a trend granularity that keeps every series readable on one
    printed page - between roughly 5 and 14 points regardless of window."""
    if days <= 14:
        return "daily"
    if days <= 90:
        return "weekly"
    return "monthly"


def _period_label_for(days: int) -> Literal["weekly", "monthly"]:
    """Map a window to the nearest of ReportService's two supported
    periods, since it only knows weekly (7 days) and monthly (30 days).

    A 180-day export still embeds a report - just one that honestly covers
    30 days, not 180 (see ReportSection.covers_export_window). Extending
    ReportService itself to any arbitrary window is a bigger change (its
    period Literal is load-bearing in the job queue, the worker, and the
    frontend types) for a label the export can already disclose truthfully
    without it.
    """
    return "weekly" if days <= 7 else "monthly"


def _classify(exc: Exception) -> AIFailure:
    """Translate any exception from an AI call into a typed, user-safe failure record.

    AIRateLimitedError is checked before AIProviderError - it's a subclass,
    so the reverse order would always match the AIProviderError branch and
    the export could never actually report a quota failure as such (the
    same ordering trap documented in endpoints/insights.py).
    """
    if isinstance(exc, AINotConfiguredError):
        return AIFailure(reason="not_configured", message=str(exc), retriable=False)
    if isinstance(exc, AIRateLimitedError):
        return AIFailure(reason="rate_limited", message=str(exc), retriable=True)
    if isinstance(exc, AIProviderError):
        return AIFailure(reason="provider_error", message=str(exc), retriable=True)
    if isinstance(exc, AIGenerationError):
        return AIFailure(reason="generation_error", message=str(exc), retriable=False)

    # An exception type this module doesn't recognize - its message may
    # carry internal detail (a stack frame, a connection string), unlike
    # the AIGenerationError family above, whose text is already curated
    # for users (see wrap_provider_error). Log the real thing, show nothing
    # but a generic, safe message.
    logger.exception("Unexpected error generating an AI export section")
    return AIFailure(reason="unexpected_error", message=_GENERIC_AI_FAILURE_MESSAGE, retriable=True)


class FullReportExportService:
    """Assemble one auditable bundle: every analytics input that feeds the
    AI, plus all three AI outputs, with each AI section degrading
    independently of the others.

    Only a missing Instagram connection fails the whole request - a quota
    limit, a missing key, or a provider outage marks just that section
    unavailable and the rest of the bundle, including every analytics
    input the AI would have seen, still returns 200. That's the point:
    this endpoint exists to be usable even when Gemini isn't.
    """

    def __init__(
        self,
        analytics_service: AnalyticsService,
        insights_service: InsightsService,
        recommendation_service: RecommendationService,
        report_service: ReportService,
    ) -> None:
        """Initialize the service with the analytics and AI service dependencies it composes."""
        self.analytics_service = analytics_service
        self.insights_service = insights_service
        self.recommendation_service = recommendation_service
        self.report_service = report_service

    def generate_export(self, user_id: int, days: ExportWindowDays) -> FullReportExportResponse:
        """Return the full auditable report bundle for one window.

        Raises InstagramAccountNotConnectedError, deliberately uncaught
        here - the endpoint maps it to 404 for the whole request, since an
        export with no account has nothing to show. Everything after this
        first call degrades independently instead.
        """
        granularity = _granularity_for(days)
        analytics = self.analytics_service.get_export_analytics(
            user_id, days, granularity, ranked_limit=RANKED_CONTENT_LIMIT, inventory_limit=INVENTORY_LIMIT
        )

        insights_section = self._build_insights_section(user_id, days)
        recommendations_section = self._build_recommendations_section(user_id, days)
        report_section = self._build_report_section(user_id, days)

        sections = (insights_section, recommendations_section, report_section)
        ai_sections_ok = sum(1 for section in sections if section.status == "ok")

        now = datetime.now(timezone.utc)
        window_start: date = (now - timedelta(days=days)).date()
        window_end: date = now.date()

        divergence = BreakdownDivergence(
            ai_sample_size=insights_section.inputs.sample.returned,
            window_sample_size=analytics.breakdowns.sample.returned,
            differs=insights_section.inputs.sample.returned != analytics.breakdowns.sample.returned,
            explanation=_BREAKDOWN_DIVERGENCE_EXPLANATION,
        )

        methodology = Methodology(
            granularity_rule=_GRANULARITY_RULE,
            report_period_rule=_REPORT_PERIOD_RULE,
            breakdown_divergence=divergence,
            media_sample_limit=MEDIA_SAMPLE_LIMIT,
            inventory_limit=analytics.inventory.limit,
            ranked_content_limit=RANKED_CONTENT_LIMIT,
            timezone="UTC",
            cache_ttl_seconds=settings.CACHE_TTL_SECONDS,
        )

        meta = ExportMeta(
            generated_at=now,
            days=days,
            window_start=window_start,
            window_end=window_end,
            username=analytics.account.username,
            instagram_user_id=analytics.account.instagram_user_id,
            ai_sections_ok=ai_sections_ok,
        )

        return FullReportExportResponse(
            meta=meta,
            methodology=methodology,
            analytics=analytics,
            insights=insights_section,
            recommendations=recommendations_section,
            report=report_section,
        )

    def _build_insights_section(self, user_id: int, days: int) -> InsightsSection:
        # Gathered directly (not just read off the service's own generation
        # path) so the audit trail is populated even when the AI call below
        # fails - see the class docstring.
        ctx = build_insights_context(self.analytics_service, user_id, days)
        result = self._run_ai_call(
            f"insights:{user_id}:{days}",
            PerformanceInsightsResponse,
            lambda: self.insights_service.get_insights(user_id, days),
        )
        return InsightsSection(
            status=result.status,
            data=result.data,
            failure=result.failure,
            served_from_cache=result.served_from_cache,
            inputs=ctx.inputs,
        )

    def _build_recommendations_section(self, user_id: int, days: int) -> RecommendationsSection:
        ctx = build_recommendations_context(self.analytics_service, user_id, days)
        result = self._run_ai_call(
            f"recommendations:{user_id}:{days}",
            RecommendationsResponse,
            lambda: self.recommendation_service.get_recommendations(user_id, days),
        )
        return RecommendationsSection(
            status=result.status,
            data=result.data,
            failure=result.failure,
            served_from_cache=result.served_from_cache,
            inputs=ctx.inputs,
        )

    def _build_report_section(self, user_id: int, days: int) -> ReportSection:
        period_label = _period_label_for(days)
        period_days: int = PERIOD_CONFIG[period_label]["days"]

        ctx = build_report_context(self.analytics_service, user_id, period_label)
        result = self._run_ai_call(
            f"report:{user_id}:{period_label}",
            PerformanceReportResponse,
            lambda: self.report_service.generate_report(user_id, period=period_label),
        )
        return ReportSection(
            status=result.status,
            data=result.data,
            failure=result.failure,
            served_from_cache=result.served_from_cache,
            inputs=ctx.inputs,
            period_label=period_label,
            period_days=period_days,
            covers_export_window=(period_days == days),
        )

    @staticmethod
    def _run_ai_call(cache_key: str, schema: type[T], call: Callable[[], T]) -> _AIResult:
        """Run one AI-backed service call, converting any failure into an
        AIResult instead of letting it propagate.

        Peeks the shared cache first purely to report served_from_cache -
        `call` still goes through the service's own get_or_generate, so
        this never triggers (or skips) an LLM request on its own.
        """
        served_from_cache = cache_get(cache_key, schema) is not None

        try:
            data = call()
        except InstagramAccountNotConnectedError:
            # A race (the account was disconnected after generate_export's
            # own analytics call above) should still surface as a 404 for
            # the whole request, not three simultaneous "AI unavailable"
            # sections - let the endpoint's handler see it.
            raise
        except Exception as exc:  # noqa: BLE001 - classified below, never silently swallowed
            return _AIResult(
                status="unavailable", data=None, failure=_classify(exc), served_from_cache=served_from_cache
            )

        return _AIResult(status="ok", data=data, failure=None, served_from_cache=served_from_cache)
