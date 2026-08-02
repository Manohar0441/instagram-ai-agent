from app.core.settings import settings
from app.integrations.ai_agent import build_agent_graph, run_agent
from app.schemas.ai import AIHealthResponse, ChatResponse
from app.services.ai_credential_service import AICredentialService
from app.services.ai_generation import (
    AIGenerationError,
    AINotConfiguredError,
    AIProviderError,
    AIRateLimitedError,
    ProviderError,
    build_llm,
    wrap_provider_error,
)
from app.services.ai_prompts import SYSTEM_PROMPT
from app.services.ai_tools import build_tools
from app.services.analytics_service import AnalyticsService
from app.services.query_analysis import REFUSAL_MESSAGE, QueryAnalysis, analyze_query

# Re-exported for backward compatibility - previously defined here.
__all__ = [
    "AIGenerationError",
    "AINotConfiguredError",
    "AIProviderError",
    "AIRateLimitedError",
    "AIService",
]


class AIService:
    """Orchestrate the conversational analytics agent.

    Builds a fresh tool set and agent graph per request, with each tool
    closed over the requesting user's ID (see ai_tools.build_tools) so a
    user's analytics can never be queried on another user's behalf. The
    agent itself only ever talks to AnalyticsService, never a repository.
    """

    def __init__(
        self,
        analytics_service: AnalyticsService,
        credential_service: AICredentialService,
    ) -> None:
        """Initialize the service with its analytics and credential dependencies."""
        self.analytics_service = analytics_service
        self.credential_service = credential_service

    def chat(self, user_id: int, message: str) -> ChatResponse:
        """Answer a natural language analytics question for the given user.

        Out-of-scope questions are refused here, before the model is reached
        - so they cost nothing, cannot be billed to the user's API key, and
        cannot carry a prompt injection into the agent.
        """
        analysis = analyze_query(message)
        if not analysis.in_scope:
            return ChatResponse(
                response=REFUSAL_MESSAGE,
                tools_used=[],
                intent="out_of_scope",
            )

        api_key = self.credential_service.resolve_api_key(user_id)

        tools = build_tools(self.analytics_service, user_id)
        graph = build_agent_graph(build_llm(api_key), tools)

        try:
            response_text, tools_used = run_agent(
                graph,
                system_prompt=self._system_prompt(analysis),
                message=message,
                recursion_limit=settings.AI_RECURSION_LIMIT,
            )
        except ProviderError as exc:
            raise wrap_provider_error(exc) from exc

        return ChatResponse(
            response=response_text,
            tools_used=tools_used,
            intent=analysis.intent,
        )

    @staticmethod
    def _system_prompt(analysis: QueryAnalysis) -> str:
        """Append what was parsed from the question to the base prompt.

        The hint is advisory - the agent still picks its own tools - but it
        makes time windows deterministic, so "last month" reliably means 30
        days rather than whatever the model infers that turn.
        """
        return f"{SYSTEM_PROMPT}\nParsed from this question: {analysis.as_hint()}\n"

    def health_check(self, user_id: int) -> AIHealthResponse:
        """Report whether the AI service is configured and ready for this user."""
        status = self.credential_service.get_status(user_id)
        return AIHealthResponse(
            status="ok" if status.configured else "unavailable",
            model=status.model,
            configured=status.configured,
            details=(
                None
                if status.configured
                else "No Gemini API key is configured for this user."
            ),
        )
