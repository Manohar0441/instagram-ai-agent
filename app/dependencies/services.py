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
from app.services.ai_credential_service import AICredentialService
from app.services.ai_service import AIService
from app.services.analytics_service import AnalyticsService
from app.services.auth_service import AuthService
from app.services.export_service import FullReportExportService
from app.services.insights_service import InsightsService
from app.services.instagram_service import InstagramService
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService
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


def get_analytics_service(
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
) -> AnalyticsService:
    """Provide an analytics service with its repository dependencies."""
    return AnalyticsService(
        instagram_account_repository,
        instagram_media_repository,
        media_insight_repository,
        account_insight_repository,
    )


def get_ai_credential_service(
    user_repository: UserRepository = Depends(get_user_repository),
) -> AICredentialService:
    """Provide an AI credential service with its repository dependencies."""
    return AICredentialService(user_repository)


def get_ai_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    credential_service: AICredentialService = Depends(get_ai_credential_service),
) -> AIService:
    """Provide an AI service with its analytics and credential dependencies."""
    return AIService(analytics_service, credential_service)


def get_insights_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    credential_service: AICredentialService = Depends(get_ai_credential_service),
) -> InsightsService:
    """Provide an insights service with its analytics and credential dependencies."""
    return InsightsService(analytics_service, credential_service)


def get_recommendation_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    credential_service: AICredentialService = Depends(get_ai_credential_service),
) -> RecommendationService:
    """Provide a recommendation service with its analytics and credential dependencies."""
    return RecommendationService(analytics_service, credential_service)


def get_report_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    credential_service: AICredentialService = Depends(get_ai_credential_service),
) -> ReportService:
    """Provide a report service with its analytics and credential dependencies."""
    return ReportService(analytics_service, credential_service)


def get_full_report_export_service(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    insights_service: InsightsService = Depends(get_insights_service),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    report_service: ReportService = Depends(get_report_service),
) -> FullReportExportService:
    """Provide a full-report export service composed from the analytics and AI services.

    FastAPI resolves each Depends() once per request, so analytics_service
    here is the same instance the three AI services below already share -
    no duplicated repositories, no second database session.
    """
    return FullReportExportService(
        analytics_service, insights_service, recommendation_service, report_service
    )
