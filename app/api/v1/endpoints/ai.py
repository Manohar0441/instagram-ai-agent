from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_ai_service
from app.models.user import User
from app.schemas.ai import AIHealthResponse, ChatRequest, ChatResponse
from app.services.ai_service import AINotConfiguredError, AIProviderError, AIService

router = APIRouter(prefix="/ai", tags=["AI Agent"])

AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with the analytics agent",
    description="Ask a natural language question about the current user's Instagram analytics.",
    operation_id="chatWithAgent",
    responses={
        status.HTTP_200_OK: {"description": "Agent response returned successfully."},
        status.HTTP_502_BAD_GATEWAY: {"description": "The AI provider request failed."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "The AI service is not configured."},
    },
)
@limiter.limit(settings.RATE_LIMIT_STRICT)
def chat(
    request: Request,
    payload: ChatRequest,
    current_user: CurrentUser,
    ai_service: AIServiceDependency,
) -> ChatResponse:
    """Answer a natural language analytics question for the current user."""
    try:
        return ai_service.chat(current_user.id, payload.message)
    except AINotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/health",
    response_model=AIHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="AI service health",
    description="Return the configuration/readiness status of the AI service and its dependencies.",
    operation_id="getAIHealth",
    responses={
        status.HTTP_200_OK: {"description": "AI service health returned successfully."},
    },
)
def health(
    current_user: CurrentUser,
    ai_service: AIServiceDependency,
) -> AIHealthResponse:
    """Return the AI service's configuration/readiness status."""
    return ai_service.health_check()
