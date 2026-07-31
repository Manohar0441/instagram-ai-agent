from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.instagram_account import InstagramAccount
from app.repositories.base import BaseRepository


class InstagramAccountRepository(BaseRepository[InstagramAccount]):
    """Handle persistence operations specific to connected Instagram accounts."""

    def __init__(self, db: Session) -> None:
        """Initialize the Instagram account repository."""
        super().__init__(InstagramAccount, db)

    def get_by_user_id(self, user_id: int) -> InstagramAccount | None:
        """Return the Instagram account connected by a platform user, if any."""
        statement = select(InstagramAccount).where(InstagramAccount.user_id == user_id)
        return self.db.scalar(statement)

    def get_by_instagram_user_id(self, instagram_user_id: str) -> InstagramAccount | None:
        """Return the connection record for a given Instagram-scoped user ID, if any."""
        statement = select(InstagramAccount).where(
            InstagramAccount.instagram_user_id == instagram_user_id
        )
        return self.db.scalar(statement)
