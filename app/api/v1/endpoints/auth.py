from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service, get_user_service
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService, InvalidCredentialsError
from app.services.user_service import (
    DuplicateEmailError,
    DuplicateUsernameError,
    UserService,
    UserServiceError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
    description="Create a new user account.",
    operation_id="registerUser",
    responses={
        status.HTTP_201_CREATED: {
            "description": "User registered successfully."
        },
        status.HTTP_409_CONFLICT: {
            "description": "The requested username or email is already in use."
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "The user could not be registered."
        },
    },
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def register(
    request: Request,
    user_data: UserCreate,
    user_service: UserServiceDependency,
) -> UserResponse:
    """Register a new user account."""
    try:
        user = user_service.create_user(user_data)
        return UserResponse.model_validate(user)
    except (DuplicateUsernameError, DuplicateEmailError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UserServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


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
