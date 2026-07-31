from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

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

    def get_latest_by_media_ids(self, media_ids: list[int]) -> dict[int, MediaInsight]:
        """Return the most recent insight snapshot for each of the given media IDs.

        Uses a single ROW_NUMBER() query rather than one lookup per media
        item, avoiding an N+1 query pattern for endpoints that need the
        latest insight across many media at once.
        """
        if not media_ids:
            return {}

        row_number = (
            func.row_number()
            .over(
                partition_by=MediaInsight.media_id,
                order_by=MediaInsight.fetched_at.desc(),
            )
            .label("row_number")
        )
        ranked = (
            select(MediaInsight, row_number)
            .where(MediaInsight.media_id.in_(media_ids))
            .subquery()
        )
        latest_insight = aliased(MediaInsight, ranked)
        statement = select(latest_insight).where(ranked.c.row_number == 1)

        results = self.db.scalars(statement).all()
        return {insight.media_id: insight for insight in results}
