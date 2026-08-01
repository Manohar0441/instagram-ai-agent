from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InstagramConnectResponse(BaseModel):
    """The Meta consent screen URL the client should navigate the user to."""

    authorization_url: str


class InstagramAccountResponse(BaseModel):
    """Public representation of a connected Instagram account.

    Deliberately excludes access_token.
    """

    id: int
    instagram_user_id: str
    username: str
    account_type: str | None
    biography: str | None
    profile_picture_url: str | None
    followers_count: int | None
    media_count: int | None
    token_expires_at: datetime | None
    connected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstagramMediaResponse(BaseModel):
    """Public representation of a fetched Instagram post or reel."""

    id: int
    media_id: str
    media_type: str
    caption: str | None
    media_url: str | None
    permalink: str | None
    posted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class MediaInsightResponse(BaseModel):
    """Latest insight metrics for a single media item."""

    media_id: str
    metrics: dict
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountInsightResponse(BaseModel):
    """Latest account-level insight metrics for a period."""

    period: str
    metrics: dict
    fetched_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InsightsResponse(BaseModel):
    """Combined account- and media-level insight snapshots."""

    account_insights: AccountInsightResponse
    media_insights: list[MediaInsightResponse]
