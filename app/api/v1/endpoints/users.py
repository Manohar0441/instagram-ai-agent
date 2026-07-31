from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_user_service
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.user_service import UserNotFoundError, UserService

router = APIRouter(prefix="/users", tags=["Users"])

UserServiceDependency = Annotated[UserService, Depends(get_user_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]
PositiveUserId = Annotated[
    int,
    Path(
        gt=0,
        description="Unique positive identifier of the user.",
    ),
]

# Two endpoints previously lived here and were removed as security defects
# (see the Milestone 9 review):
#
#   POST /users  - an unauthenticated duplicate of POST /auth/register that
#                  also bypassed that endpoint's strict brute-force rate
#                  limit. Registration now has exactly one entry point.
#   GET  /users  - returned every user record, including email addresses,
#                  with no authentication at all. There is no role system
#                  here that could legitimately gate a list-all-users
#                  operation, and no product feature needs one.


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user",
    description="Return a user account record by ID. Users may only retrieve their own record.",
    operation_id="getUser",
    responses={
        status.HTTP_200_OK: {
            "description": "User returned successfully."
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Missing, invalid, or expired access token."
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "No such user exists, or it is not the requesting user's record."
        },
    },
)
def get_user(
    user_id: PositiveUserId,
    current_user: CurrentUser,
    user_service: UserServiceDependency,
) -> UserResponse:
    """Return a user record, provided it belongs to the requesting user."""
    # Another user's ID returns 404 rather than 403: a 403 would confirm
    # that the ID exists, turning this into a user-enumeration oracle.
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} was not found.",
        )

    try:
        user = user_service.get_user(user_id)
        return UserResponse.model_validate(user)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
