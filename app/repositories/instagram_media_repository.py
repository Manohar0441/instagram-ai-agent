from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.instagram_media import InstagramMedia
from app.repositories.base import BaseRepository


class InstagramMediaRepository(BaseRepository[InstagramMedia]):
    """Handle persistence operations specific to Instagram media."""

    def __init__(self, db: Session) -> None:
        """Initialize the Instagram media repository."""
        super().__init__(InstagramMedia, db)

    def get_by_media_id(self, media_id: str) -> InstagramMedia | None:
        """Return a media item by its Instagram-scoped media ID, if any."""
        statement = select(InstagramMedia).where(InstagramMedia.media_id == media_id)
        return self.db.scalar(statement)

    def list_by_account_id(self, instagram_account_id: int) -> list[InstagramMedia]:
        """Return all media for a connected account, most recently posted first."""
        statement = (
            select(InstagramMedia)
            .where(InstagramMedia.instagram_account_id == instagram_account_id)
            .order_by(InstagramMedia.posted_at.desc().nullslast())
        )
        return list(self.db.scalars(statement).all())
