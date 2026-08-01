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


class AIKeyRejectedError(AIGenerationError):
    """Raised when Gemini rejects a user-supplied API key as unusable."""


# Re-exported so callers can catch provider failures without importing a
# private langchain_google_genai module themselves.
ProviderError = GoogleGenerativeAIError

# Substrings Gemini uses for an unusable credential, as opposed to quota,
# outage, or model-configuration failures. Matching on message text is
# unpleasant, but langchain_google_genai raises one exception type for
# every failure, so there is nothing structured to branch on.
_REJECTED_KEY_MARKERS = ("API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED")


def build_llm(api_key: str) -> ChatGoogleGenerativeAI:
    """Build a chat model client for a specific caller's API key.

    The model and temperature stay server configuration; only the
    credential varies per user.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=settings.GEMINI_MODEL,
        temperature=settings.GEMINI_TEMPERATURE,
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
