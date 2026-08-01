from langchain_google_genai import ChatGoogleGenerativeAI

# Not part of langchain_google_genai's public API (no top-level export
# exists), but it's the base exception every failure from this client
# raises - see the verification in the Milestone 11 Gemini migration.
from langchain_google_genai._common import GoogleGenerativeAIError

from app.core.settings import settings


class AIGenerationError(Exception):
    """Base exception for AI generation failures, shared across AI services."""


class AINotConfiguredError(AIGenerationError):
    """Raised when the Gemini API key is not configured."""


class AIProviderError(AIGenerationError):
    """Raised when a Gemini API call fails."""


# Re-exported so callers can catch provider failures without importing a
# private langchain_google_genai module themselves.
ProviderError = GoogleGenerativeAIError


def ensure_configured() -> None:
    """Raise AINotConfiguredError if the Gemini API key isn't set."""
    if not settings.GOOGLE_API_KEY:
        raise AINotConfiguredError("AI features are not configured. Set GOOGLE_API_KEY.")


def build_llm() -> ChatGoogleGenerativeAI:
    """Build a chat model client from application settings."""
    return ChatGoogleGenerativeAI(
        google_api_key=settings.GOOGLE_API_KEY,
        model=settings.GEMINI_MODEL,
        temperature=settings.GEMINI_TEMPERATURE,
    )
