from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media_insight import MediaInsight
from app.repositories.base import BaseRepository


class MediaInsightRepository(BaseRepository[MediaInsight]):
    """Handle persistence operations specific to media insight snapshots."""

    def __init__(self, db: Session) -> None:
        """Initialize the media insight repository."""
        super().__init__(MediaInsight, db)

    def create_snapshot(self, media_id: int, metrics: dict) -> MediaInsight:
        """Persist a new insight metrics snapshot for a media item."""
        return self.create(MediaInsight(media_id=media_id, metrics=metrics))

    def get_latest_by_media_id(self, media_id: int) -> MediaInsight | None:
        """Return the most recent insight snapshot for a media item, if any."""
        statement = (
            select(MediaInsight)
            .where(MediaInsight.media_id == media_id)
            .order_by(MediaInsight.fetched_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)
