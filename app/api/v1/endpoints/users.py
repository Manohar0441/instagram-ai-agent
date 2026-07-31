from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.dependencies.services import get_user_service
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import (
    DuplicateEmailError,
    DuplicateUsernameError,
    UserNotFoundError,
    UserService,
    UserServiceError,
)

router = APIRouter(prefix="/users", tags=["Users"])

UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
PositiveUserId = Annotated[
    int,
    Path(
        gt=0,
        description="Unique positive identifier of the user.",
    ),
]


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a user account record.",
    operation_id="createUser",
    responses={
        status.HTTP_201_CREATED: {
            "description": "User created successfully."
        },
        status.HTTP_409_CONFLICT: {
            "description": "A user with the requested username or email already exists."
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "The user could not be created."
        },
    },
)
def create_user(
    user_data: UserCreate,
    user_service: UserServiceDependency,
) -> UserResponse:
    """Create a user through the service layer."""
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


@router.get(
    "",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List users",
    description="Return all user account records.",
    operation_id="listUsers",
    responses={
        status.HTTP_200_OK: {
            "description": "Users returned successfully."
        },
    },
)
def list_users(
    user_service: UserServiceDependency,
) -> list[UserResponse]:
    """List users through the service layer."""
    users = user_service.list_users()
    return [UserResponse.model_validate(user) for user in users]


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user",
    description="Return a single user account record by ID.",
    operation_id="getUser",
    responses={
        status.HTTP_200_OK: {
            "description": "User returned successfully."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "No user exists with the requested ID."
        },
    },
)
def get_user(
    user_id: PositiveUserId,
    user_service: UserServiceDependency,
) -> UserResponse:
    """Get a user through the service layer."""
    try:
        user = user_service.get_user(user_id)
        return UserResponse.model_validate(user)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
