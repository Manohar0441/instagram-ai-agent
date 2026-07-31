from fastapi import Depends

from app.core.settings import settings
from app.dependencies.repositories import (
    get_account_insight_repository,
    get_instagram_account_repository,
    get_instagram_media_repository,
    get_media_insight_repository,
    get_user_repository,
)
from app.integrations.instagram_client import InstagramGraphClient
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.instagram_service import InstagramService
from app.services.user_service import UserService


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> UserService:
    """Provide a user service with its repository dependencies."""
    return UserService(user_repository)


def get_auth_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Provide an auth service with its repository dependencies."""
    return AuthService(user_repository)


def get_instagram_client() -> InstagramGraphClient:
    """Provide a Graph API client configured from application settings."""
    return InstagramGraphClient(
        app_id=settings.INSTAGRAM_APP_ID or "",
        app_secret=settings.INSTAGRAM_APP_SECRET or "",
        api_version=settings.INSTAGRAM_GRAPH_API_VERSION,
    )


def get_instagram_service(
    instagram_account_repository: InstagramAccountRepository = Depends(
        get_instagram_account_repository
    ),
    instagram_media_repository: InstagramMediaRepository = Depends(
        get_instagram_media_repository
    ),
    media_insight_repository: MediaInsightRepository = Depends(get_media_insight_repository),
    account_insight_repository: AccountInsightRepository = Depends(
        get_account_insight_repository
    ),
    instagram_client: InstagramGraphClient = Depends(get_instagram_client),
) -> InstagramService:
    """Provide an Instagram service with its repository and API client dependencies."""
    return InstagramService(
        instagram_account_repository,
        instagram_media_repository,
        media_insight_repository,
        account_insight_repository,
        instagram_client,
    )
