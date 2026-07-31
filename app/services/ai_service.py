import openai

from app.core.settings import settings
from app.integrations.ai_agent import build_agent_graph, run_agent
from app.schemas.ai import AIHealthResponse, ChatResponse
from app.services.ai_generation import (
    AIGenerationError,
    AINotConfiguredError,
    AIProviderError,
    build_llm,
    ensure_configured,
)
from app.services.ai_prompts import SYSTEM_PROMPT
from app.services.ai_tools import build_tools
from app.services.analytics_service import AnalyticsService

# Re-exported for backward compatibility - previously defined here.
__all__ = ["AIGenerationError", "AINotConfiguredError", "AIProviderError", "AIService"]


class AIService:
    """Orchestrate the conversational analytics agent.

    Builds a fresh tool set and agent graph per request, with each tool
    closed over the requesting user's ID (see ai_tools.build_tools) so a
    user's analytics can never be queried on another user's behalf. The
    agent itself only ever talks to AnalyticsService, never a repository.
    """

    def __init__(self, analytics_service: AnalyticsService) -> None:
        """Initialize the service with its analytics dependency."""
        self.analytics_service = analytics_service

    def chat(self, user_id: int, message: str) -> ChatResponse:
        """Answer a natural language analytics question for the given user."""
        ensure_configured()

        tools = build_tools(self.analytics_service, user_id)
        graph = build_agent_graph(build_llm(), tools)

        try:
            response_text, tools_used = run_agent(
                graph,
                system_prompt=SYSTEM_PROMPT,
                message=message,
                recursion_limit=settings.AI_RECURSION_LIMIT,
            )
        except openai.OpenAIError as exc:
            raise AIProviderError(f"The AI provider request failed: {exc}") from exc

        return ChatResponse(response=response_text, tools_used=tools_used)

    def health_check(self) -> AIHealthResponse:
        """Report whether the AI service is configured and ready to serve requests."""
        configured = bool(settings.OPENAI_API_KEY)
        return AIHealthResponse(
            status="ok" if configured else "unavailable",
            model=settings.OPENAI_MODEL,
            openai_configured=configured,
            details=None if configured else "OPENAI_API_KEY is not configured.",
        )
