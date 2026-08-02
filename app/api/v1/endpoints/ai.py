from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_ai_credential_service, get_ai_service
from app.models.user import User
from app.schemas.ai import (
    AIHealthResponse,
    AIKeyStatusResponse,
    AIKeyUpdateRequest,
    ChatRequest,
    ChatResponse,
)
from app.services.ai_credential_service import (
    AICredentialService,
    AIKeyRejectedError,
    AIUserNotFoundError,
)
from app.services.ai_service import (
    AINotConfiguredError,
    AIProviderError,
    AIRateLimitedError,
    AIService,
)

router = APIRouter(prefix="/ai", tags=["AI Agent"])

AIServiceDependency = Annotated[AIService, Depends(get_ai_service)]
AICredentialServiceDependency = Annotated[
    AICredentialService, Depends(get_ai_credential_service)
]
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
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "The AI provider's rate limit was reached."},
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
    # AIRateLimitedError is a subclass of AIProviderError - it must be
    # caught first, or its except clause is unreachable.
    except AIRateLimitedError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
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
    return ai_service.health_check(current_user.id)


@router.get(
    "/key",
    response_model=AIKeyStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Gemini API key status",
    description=(
        "Report whether a Gemini API key is available for the current user, "
        "where it comes from, and a short hint. Never returns the key itself."
    ),
    operation_id="getAIKeyStatus",
    responses={
        status.HTTP_200_OK: {"description": "Key status returned successfully."},
    },
)
def get_key_status(
    current_user: CurrentUser,
    credential_service: AICredentialServiceDependency,
) -> AIKeyStatusResponse:
    """Return the current user's Gemini API key status."""
    return credential_service.get_status(current_user.id)


@router.put(
    "/key",
    response_model=AIKeyStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Set the Gemini API key",
    description=(
        "Store a Gemini API key for the current user, replacing any existing "
        "one. The key is verified with the provider and encrypted at rest."
    ),
    operation_id="setAIKey",
    responses={
        status.HTTP_200_OK: {"description": "Key stored successfully."},
        status.HTTP_400_BAD_REQUEST: {"description": "Gemini rejected the API key."},
        status.HTTP_404_NOT_FOUND: {"description": "The user no longer exists."},
    },
)
@limiter.limit(settings.RATE_LIMIT_STRICT)
def set_key(
    request: Request,
    payload: AIKeyUpdateRequest,
    current_user: CurrentUser,
    credential_service: AICredentialServiceDependency,
) -> AIKeyStatusResponse:
    """Store and verify a Gemini API key for the current user."""
    try:
        return credential_service.set_api_key(current_user.id, payload.api_key)
    except AIKeyRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AIUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/key",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove the Gemini API key",
    description=(
        "Delete the current user's stored Gemini API key. AI features fall "
        "back to the server-wide key, or become unavailable if none is set."
    ),
    operation_id="clearAIKey",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Key removed successfully."},
        status.HTTP_404_NOT_FOUND: {"description": "The user no longer exists."},
    },
)
def clear_key(
    current_user: CurrentUser,
    credential_service: AICredentialServiceDependency,
) -> None:
    """Remove the current user's stored Gemini API key."""
    try:
        credential_service.clear_api_key(current_user.id)
    except AIUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
