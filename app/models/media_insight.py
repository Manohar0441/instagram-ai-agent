from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MediaInsight(Base):
    """A point-in-time snapshot of insight metrics for a single media item.

    Metrics are stored as a JSON blob (rather than fixed columns) so new
    Graph API metrics can be added without a schema migration.
    """

    __tablename__ = "media_insights"

    id: Mapped[int] = mapped_column(primary_key=True)

    media_id: Mapped[int] = mapped_column(
        ForeignKey("instagram_media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    metrics: Mapped[dict] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
    )

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
