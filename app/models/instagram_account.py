from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InstagramAccount(Base):
    """A connected Instagram Business/Creator account, one per platform user."""

    __tablename__ = "instagram_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    instagram_user_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    followers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Encrypted long-lived user access token; never returned via the API.
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
