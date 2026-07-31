from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.repositories.user_repository import UserRepository


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Provide a user repository backed by the request database session."""
    return UserRepository(db)


def get_instagram_account_repository(
    db: Session = Depends(get_db),
) -> InstagramAccountRepository:
    """Provide an Instagram account repository backed by the request database session."""
    return InstagramAccountRepository(db)


def get_instagram_media_repository(
    db: Session = Depends(get_db),
) -> InstagramMediaRepository:
    """Provide an Instagram media repository backed by the request database session."""
    return InstagramMediaRepository(db)


def get_media_insight_repository(
    db: Session = Depends(get_db),
) -> MediaInsightRepository:
    """Provide a media insight repository backed by the request database session."""
    return MediaInsightRepository(db)


def get_account_insight_repository(
    db: Session = Depends(get_db),
) -> AccountInsightRepository:
    """Provide an account insight repository backed by the request database session."""
    return AccountInsightRepository(db)
