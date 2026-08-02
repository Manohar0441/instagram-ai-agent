import pytest

from app.services.ai_generation import (
    AIGenerationError,
    AINotConfiguredError,
    AIProviderError,
    AIRateLimitedError,
)
from app.services.export_service import _classify, _granularity_for, _period_label_for

pytestmark = pytest.mark.unit


class TestGranularityFor:
    """Every window should read as 5-14 points on a printed chart - not a
    single dot (30 days at monthly) or 365 rows (365 days at daily)."""

    @pytest.mark.parametrize(
        "days,expected",
        [
            (7, "daily"),
            (14, "daily"),
            (15, "weekly"),
            (30, "weekly"),
            (90, "weekly"),
            (91, "monthly"),
            (180, "monthly"),
            (365, "monthly"),
        ],
    )
    def test_boundaries(self, days, expected):
        assert _granularity_for(days) == expected


class TestPeriodLabelFor:
    @pytest.mark.parametrize(
        "days,expected",
        [(7, "weekly"), (8, "monthly"), (14, "monthly"), (30, "monthly"), (365, "monthly")],
    )
    def test_boundaries(self, days, expected):
        assert _period_label_for(days) == expected


class TestClassify:
    def test_not_configured(self):
        failure = _classify(AINotConfiguredError("Add a Gemini API key in Settings."))
        assert failure.reason == "not_configured"
        assert failure.retriable is False

    def test_rate_limited_wins_over_provider_error(self):
        """AIRateLimitedError subclasses AIProviderError - checking the
        broader type first would mean a quota failure could never actually
        be reported as rate_limited (the same ordering trap documented at
        app/api/v1/endpoints/insights.py:50-51)."""
        failure = _classify(AIRateLimitedError("Gemini's rate limit was reached."))
        assert failure.reason == "rate_limited"
        assert failure.retriable is True

    def test_generic_provider_error(self):
        failure = _classify(AIProviderError("The AI provider request failed."))
        assert failure.reason == "provider_error"
        assert failure.retriable is True

    def test_other_generation_error_is_not_retriable(self):
        """Anything else under AIGenerationError (e.g. a missing-user
        credential error) isn't a transient failure worth retrying."""
        failure = _classify(AIGenerationError("User with ID 9 was not found."))
        assert failure.reason == "generation_error"
        assert failure.retriable is False

    def test_unexpected_error_does_not_leak_internal_detail(self):
        failure = _classify(RuntimeError("connection string: postgres://user:hunter2@host"))
        assert failure.reason == "unexpected_error"
        assert failure.retriable is True
        assert "hunter2" not in failure.message
        assert "postgres://" not in failure.message
