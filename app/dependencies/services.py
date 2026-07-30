from fastapi import Depends

from app.dependencies.repositories import get_user_repository
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    """Provide a user service with its repository dependencies."""
    return UserService(user_repository)
