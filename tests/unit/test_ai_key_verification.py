import pytest
from langchain_google_genai._common import GoogleGenerativeAIError

import app.services.ai_generation as generation
from app.services.ai_generation import (
    AIKeyRejectedError,
    AIProviderError,
    AIRateLimitedError,
    verify_api_key,
    wrap_provider_error,
)

pytestmark = pytest.mark.unit


class FailingLLM:
    def __init__(self, message: str) -> None:
        self.message = message

    def invoke(self, _prompt):
        raise GoogleGenerativeAIError(self.message)


@pytest.fixture
def failing_llm(monkeypatch):
    """Make build_llm return a client that fails with a chosen message."""

    def _use(message: str):
        monkeypatch.setattr(generation, "build_llm", lambda api_key: FailingLLM(message))

    return _use


# The exact strings the live API returns. A well-formed but wrong key and a
# malformed one fail differently, and both must be treated as rejections.
WRONG_KEY_ERROR = (
    "Error calling model 'gemini-2.0-flash' (UNAUTHENTICATED): 401 UNAUTHENTICATED. "
    "{'error': {'code': 401, 'message': 'Request had invalid authentication "
    "credentials.', 'status': 'UNAUTHENTICATED'}}"
)
MALFORMED_KEY_ERROR = (
    "Error calling model 'gemini-2.0-flash' (INVALID_ARGUMENT): 400 INVALID_ARGUMENT. "
    "{'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API "
    "key.', 'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'API_KEY_INVALID'}]}}"
)


class TestRejection:
    @pytest.mark.parametrize(
        "message",
        [WRONG_KEY_ERROR, MALFORMED_KEY_ERROR],
        ids=["wrong_key_401", "malformed_key_400"],
    )
    def test_credential_failures_are_rejected(self, failing_llm, message):
        failing_llm(message)

        with pytest.raises(AIKeyRejectedError):
            verify_api_key("AQ.some-candidate-key")


class TestTolerance:
    """Everything that is not a credential problem must let the key through:
    refusing a valid key because Gemini was briefly unavailable is worse than
    storing one that turns out to be wrong."""

    @pytest.mark.parametrize(
        "message",
        [
            "429 RESOURCE_EXHAUSTED. Quota exceeded for this project.",
            "503 UNAVAILABLE. The service is currently unavailable.",
            "504 DEADLINE_EXCEEDED.",
            "404 NOT_FOUND. models/gemini-9.9-ultra is not found.",
        ],
        ids=["quota", "outage", "timeout", "bad_model"],
    )
    def test_non_credential_failures_are_tolerated(self, failing_llm, message):
        failing_llm(message)

        verify_api_key("AQ.some-candidate-key")  # must not raise

    def test_a_working_key_is_accepted(self, monkeypatch):
        class WorkingLLM:
            def invoke(self, _prompt):
                return "pong"

        monkeypatch.setattr(generation, "build_llm", lambda api_key: WorkingLLM())

        verify_api_key("AQ.some-candidate-key")


# The exact 429 payload Gemini's free tier returns, in full - this is what
# used to leak straight into the chat UI as a wall of raw JSON.
QUOTA_ERROR = (
    "Error calling model 'gemini-2.5-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED. "
    "{'error': {'code': 429, 'message': 'You exceeded your current quota, please check "
    "your plan and billing details.', 'status': 'RESOURCE_EXHAUSTED', "
    "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', "
    "'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_"
    "free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, "
    "{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '45s'}]}}"
)


class TestWrapProviderError:
    """wrap_provider_error is what stands between a raw provider exception
    and the user-facing chat/insights/report error - it must never leak the
    provider's payload, and a rate limit must be told apart from any other
    failure so the frontend can show distinct copy."""

    def test_quota_exhaustion_is_a_rate_limit_error(self):
        result = wrap_provider_error(GoogleGenerativeAIError(QUOTA_ERROR))

        assert isinstance(result, AIRateLimitedError)
        assert "rate limit" in str(result).lower()

    def test_rate_limit_message_does_not_leak_the_raw_payload(self):
        result = wrap_provider_error(GoogleGenerativeAIError(QUOTA_ERROR))

        assert "generativelanguage.googleapis.com" not in str(result)
        assert "RESOURCE_EXHAUSTED" not in str(result)
        assert "quotaMetric" not in str(result)

    def test_other_provider_failures_are_a_generic_error(self):
        result = wrap_provider_error(
            GoogleGenerativeAIError("503 UNAVAILABLE. The service is currently unavailable.")
        )

        assert isinstance(result, AIProviderError)
        assert not isinstance(result, AIRateLimitedError)
        assert "UNAVAILABLE" not in str(result)
