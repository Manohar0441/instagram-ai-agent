from langchain_openai import ChatOpenAI

from app.core.settings import settings


class AIGenerationError(Exception):
    """Base exception for AI generation failures, shared across AI services."""


class AINotConfiguredError(AIGenerationError):
    """Raised when the OpenAI API key is not configured."""


class AIProviderError(AIGenerationError):
    """Raised when an OpenAI API call fails."""


def ensure_configured() -> None:
    """Raise AINotConfiguredError if the OpenAI API key isn't set."""
    if not settings.OPENAI_API_KEY:
        raise AINotConfiguredError("AI features are not configured. Set OPENAI_API_KEY.")


def build_llm() -> ChatOpenAI:
    """Build a chat model client from application settings."""
    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        temperature=settings.OPENAI_TEMPERATURE,
    )
