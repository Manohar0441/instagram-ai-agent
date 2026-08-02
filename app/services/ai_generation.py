import logging

from langchain_google_genai import ChatGoogleGenerativeAI

# Not part of langchain_google_genai's public API (no top-level export
# exists), but it's the base exception every failure from this client
# raises - see the verification in the Milestone 11 Gemini migration.
from langchain_google_genai._common import GoogleGenerativeAIError

from app.core.settings import settings

logger = logging.getLogger(__name__)


class AIGenerationError(Exception):
    """Base exception for AI generation failures, shared across AI services."""


class AINotConfiguredError(AIGenerationError):
    """Raised when no Gemini API key is available for the requesting user."""


class AIProviderError(AIGenerationError):
    """Raised when a Gemini API call fails."""


class AIRateLimitedError(AIProviderError):
    """Raised when Gemini rejects a request for exceeding its rate limit or quota."""


class AIKeyRejectedError(AIGenerationError):
    """Raised when Gemini rejects a user-supplied API key as unusable."""


# Re-exported so callers can catch provider failures without importing a
# private langchain_google_genai module themselves.
ProviderError = GoogleGenerativeAIError

# Substrings Gemini uses for an unusable credential, as opposed to quota,
# outage, or model-configuration failures. Matching on message text is
# unpleasant, but langchain_google_genai raises one exception type for
# every failure, so there is nothing structured to branch on.
#
# Verified against the live API rather than guessed - it returns two
# different shapes: a well-formed but wrong key gives 401 UNAUTHENTICATED,
# while a malformed one gives 400 INVALID_ARGUMENT / API_KEY_INVALID.
_REJECTED_KEY_MARKERS = (
    "UNAUTHENTICATED",
    "API_KEY_INVALID",
    "API key not valid",
    "PERMISSION_DENIED",
)

# Gemini's free-tier quota errors come back as RESOURCE_EXHAUSTED / HTTP 429.
_RATE_LIMIT_MARKERS = ("RESOURCE_EXHAUSTED", "429")


def wrap_provider_error(exc: ProviderError) -> AIProviderError:
    """Translate a raw provider exception into a short, user-facing error.

    langchain_google_genai's exception text is a multi-line dump of the
    provider's full error payload - a 429 alone runs to several hundred
    characters of nested JSON (retry links, quota IDs, help URLs). That is
    useful in a log, not in a chat bubble, so only a clean summary is kept
    for the message shown to the user; the raw exception is still available
    to callers via exception chaining (`raise ... from exc`) and is logged
    here regardless of which branch is taken.
    """
    text = str(exc)
    logger.warning("AI provider request failed: %s", text)
    if any(marker in text for marker in _RATE_LIMIT_MARKERS):
        return AIRateLimitedError(
            "Gemini's rate limit was reached. Wait a moment and try again."
        )
    return AIProviderError("The AI provider request failed. Please try again in a moment.")


# Gemini's own client rejects any deadline below this outright, with a 400
# INVALID_ARGUMENT raised before the request is even sent - "Manually set
# deadline Xs is too short. Minimum allowed deadline is 10s." Clamping here
# means a misconfigured GEMINI_TIMEOUT_SECONDS (e.g. tuned too aggressively
# for a downstream gateway's own timeout ceiling) fails safe by *widening*
# the timeout rather than making every single call fail instantly.
_GEMINI_MIN_TIMEOUT_SECONDS = 10


def build_llm(api_key: str) -> ChatGoogleGenerativeAI:
    """Build a chat model client for a specific caller's API key.

    The model and temperature stay server configuration; only the
    credential varies per user.

    Explicit timeout and a capped retry count: left at their defaults, a
    flapping provider can retry internally (default max_retries=6) with no
    bound on wall-clock time per call. That's a real risk for any request
    path that makes several sequential calls, like the full-report export.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=settings.GEMINI_MODEL,
        temperature=settings.GEMINI_TEMPERATURE,
        timeout=max(settings.GEMINI_TIMEOUT_SECONDS, _GEMINI_MIN_TIMEOUT_SECONDS),
        max_retries=2,
    )


def verify_api_key(api_key: str) -> None:
    """Check a candidate Gemini API key against the provider, best effort.

    Only an unambiguous credential rejection raises AIKeyRejectedError.
    Quota limits, network failures, and model misconfiguration are allowed
    through: refusing a valid key because Gemini was momentarily
    unreachable is worse than storing one that turns out to be wrong,
    which the user discovers on their next AI request with the same error
    they would have seen anyway.
    """
    try:
        build_llm(api_key).invoke("ping")
    except GoogleGenerativeAIError as exc:
        if any(marker in str(exc) for marker in _REJECTED_KEY_MARKERS):
            raise AIKeyRejectedError(
                "Gemini rejected this API key. Check it and try again."
            ) from exc
        # Deliberately not fatal - see the docstring. The key is stored and
        # the user finds out on their next request if it really is broken.
        logger.warning("Gemini API key check was inconclusive: %s", exc)
