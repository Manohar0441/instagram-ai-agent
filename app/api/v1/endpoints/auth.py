from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService, InvalidCredentialsError

# There is deliberately no POST /auth/register route. This is a single-user
# app - the one account is created directly in the database with
# `python -m scripts.create_user` (see Documents/DEPLOYMENT.md) - so that
# self-service registration is unreachable by design, not merely unlinked
# from the UI.

router = APIRouter(prefix="/auth", tags=["Auth"])

AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Login",
    description="Authenticate with an email and password (submit email as 'username') to obtain an access token.",
    operation_id="login",
    responses={
        status.HTTP_200_OK: {
            "description": "Authentication successful."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid email or password."
        },
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDependency,
) -> Token:
    """Authenticate a user and issue a JWT access token."""
    try:
        access_token = auth_service.login(
            email=form_data.username,
            password=form_data.password,
        )
        return Token(access_token=access_token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user",
    description="Return the profile of the currently authenticated user.",
    operation_id="getCurrentUser",
    responses={
        status.HTTP_200_OK: {
            "description": "Current user returned successfully."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing, invalid, or expired access token."
        },
    },
)
def get_me(current_user: CurrentUser) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
