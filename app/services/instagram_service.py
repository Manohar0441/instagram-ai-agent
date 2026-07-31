from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, TypeVar

import jwt

from app.core.settings import settings
from app.integrations.instagram_client import InstagramAPIError, InstagramGraphClient
from app.models.account_insight import AccountInsight
from app.models.instagram_account import InstagramAccount
from app.models.instagram_media import InstagramMedia
from app.models.media_insight import MediaInsight
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.utils.encryption import decrypt_token, encrypt_token
from app.utils.jwt import create_oauth_state_token, decode_oauth_state_token

T = TypeVar("T")

MAX_MEDIA_INSIGHTS_PER_REQUEST = 25
DEFAULT_ACCOUNT_INSIGHTS_PERIOD = "day"

# A distinct AccountInsight "period" value used to snapshot profile fields
# (followers_count, media_count) over time, so the Analytics Engine can
# compute follower growth. Not a real Graph API insights period.
PROFILE_SNAPSHOT_PERIOD = "profile"


class InstagramServiceError(Exception):
    """Base exception for Instagram integration failures."""


class InstagramNotConfiguredError(InstagramServiceError):
    """Raised when required Instagram app credentials are not configured."""


class InvalidOAuthStateError(InstagramServiceError):
    """Raised when an OAuth callback's state parameter is missing or invalid."""


class InstagramAccountNotConnectedError(InstagramServiceError):
    """Raised when a user has no connected Instagram account."""


class InstagramAccountAlreadyConnectedError(InstagramServiceError):
    """Raised when a user attempts to connect a second Instagram account."""


class DuplicateInstagramAccountError(InstagramServiceError):
    """Raised when the Instagram account is already connected to another user."""


class InstagramTokenExpiredError(InstagramServiceError):
    """Raised when the stored access token is expired, invalid, or revoked."""


class InstagramOAuthError(InstagramServiceError):
    """Raised when an OAuth exchange or Graph API call fails."""


class InstagramService:
    """Coordinate the Instagram OAuth flow and Graph API data retrieval."""

    def __init__(
        self,
        instagram_account_repository: InstagramAccountRepository,
        instagram_media_repository: InstagramMediaRepository,
        media_insight_repository: MediaInsightRepository,
        account_insight_repository: AccountInsightRepository,
        instagram_client: InstagramGraphClient,
    ) -> None:
        """Initialize the service with required repositories and API client."""
        self.instagram_account_repository = instagram_account_repository
        self.instagram_media_repository = instagram_media_repository
        self.media_insight_repository = media_insight_repository
        self.account_insight_repository = account_insight_repository
        self.instagram_client = instagram_client

    def get_authorization_url(self, user_id: int) -> str:
        """Build the Meta consent screen URL for a user to start the OAuth flow."""
        self._ensure_configured()
        state = create_oauth_state_token(user_id)
        return self.instagram_client.build_authorization_url(
            redirect_uri=settings.INSTAGRAM_REDIRECT_URI,
            state=state,
        )

    def connect_account(self, code: str, state: str) -> InstagramAccount:
        """Complete the OAuth callback and persist the connected Instagram account."""
        self._ensure_configured()
        user_id = self._decode_state(state)

        if self.instagram_account_repository.get_by_user_id(user_id) is not None:
            raise InstagramAccountAlreadyConnectedError(
                "This user already has a connected Instagram account. Disconnect it first."
            )

        short_lived = self._call(
            self.instagram_client.exchange_code_for_user_token,
            code=code,
            redirect_uri=settings.INSTAGRAM_REDIRECT_URI,
        )
        long_lived = self._call(
            self.instagram_client.exchange_for_long_lived_token,
            short_lived_token=short_lived["access_token"],
        )
        long_lived_token = long_lived["access_token"]
        token_expires_at = self._compute_expiry(long_lived.get("expires_in"))

        instagram_user_id, facebook_page_id = self._discover_instagram_account(long_lived_token)

        if self.instagram_account_repository.get_by_instagram_user_id(instagram_user_id) is not None:
            raise DuplicateInstagramAccountError(
                "This Instagram account is already connected to another user."
            )

        profile = self._call(
            self.instagram_client.get_profile,
            instagram_user_id=instagram_user_id,
            access_token=long_lived_token,
        )

        account = InstagramAccount(
            user_id=user_id,
            instagram_user_id=instagram_user_id,
            facebook_page_id=facebook_page_id,
            username=profile.get("username", ""),
            account_type=profile.get("account_type"),
            biography=profile.get("biography"),
            profile_picture_url=profile.get("profile_picture_url"),
            followers_count=profile.get("followers_count"),
            media_count=profile.get("media_count"),
            access_token=encrypt_token(long_lived_token),
            token_expires_at=token_expires_at,
        )

        created_account = self.instagram_account_repository.create(account)
        self._snapshot_profile_counts(created_account)
        self._commit()
        return created_account

    def get_profile(self, user_id: int) -> InstagramAccount:
        """Refresh and return the connected account's profile information."""
        account = self._get_connected_account(user_id)
        access_token = self._valid_access_token(account)

        profile = self._call(
            self.instagram_client.get_profile,
            instagram_user_id=account.instagram_user_id,
            access_token=access_token,
        )

        account.username = profile.get("username", account.username)
        account.account_type = profile.get("account_type", account.account_type)
        account.biography = profile.get("biography")
        account.profile_picture_url = profile.get("profile_picture_url")
        account.followers_count = profile.get("followers_count")
        account.media_count = profile.get("media_count")

        self._snapshot_profile_counts(account)
        self._commit()
        return account

    def get_media(self, user_id: int, limit: int = 25) -> list[InstagramMedia]:
        """Fetch recent posts/reels from Graph API and upsert them into storage."""
        account = self._get_connected_account(user_id)
        access_token = self._valid_access_token(account)

        media_items = self._call(
            self.instagram_client.get_media,
            instagram_user_id=account.instagram_user_id,
            access_token=access_token,
            limit=limit,
        )

        for item in media_items:
            self._upsert_media(account.id, item)

        self._commit()
        return self.instagram_media_repository.list_by_account_id(account.id)

    def get_insights(
        self, user_id: int
    ) -> tuple[AccountInsight, list[tuple[InstagramMedia, MediaInsight]]]:
        """Fetch and store account-level insights and insights for stored media."""
        account = self._get_connected_account(user_id)
        access_token = self._valid_access_token(account)

        account_metrics = self._call(
            self.instagram_client.get_account_insights,
            instagram_user_id=account.instagram_user_id,
            access_token=access_token,
            period=DEFAULT_ACCOUNT_INSIGHTS_PERIOD,
        )
        account_insight = self.account_insight_repository.create_snapshot(
            instagram_account_id=account.id,
            period=DEFAULT_ACCOUNT_INSIGHTS_PERIOD,
            metrics=account_metrics,
        )

        media_list = self.instagram_media_repository.list_by_account_id(account.id)
        media_insight_pairs: list[tuple[InstagramMedia, MediaInsight]] = []

        for media in media_list[:MAX_MEDIA_INSIGHTS_PER_REQUEST]:
            metrics = self._call(
                self.instagram_client.get_media_insights,
                media_id=media.media_id,
                media_type=media.media_type,
                access_token=access_token,
            )
            insight = self.media_insight_repository.create_snapshot(media.id, metrics)
            media_insight_pairs.append((media, insight))

        self._commit()
        return account_insight, media_insight_pairs

    def disconnect_account(self, user_id: int) -> None:
        """Remove a connected Instagram account and all its stored data."""
        account = self._get_connected_account(user_id)
        self.instagram_account_repository.delete(account.id)
        self._commit()

    def _snapshot_profile_counts(self, account: InstagramAccount) -> None:
        """Record a point-in-time snapshot of followers/media counts for trend analysis."""
        self.account_insight_repository.create_snapshot(
            instagram_account_id=account.id,
            period=PROFILE_SNAPSHOT_PERIOD,
            metrics={
                "followers_count": account.followers_count,
                "media_count": account.media_count,
            },
        )

    def _get_connected_account(self, user_id: int) -> InstagramAccount:
        account = self.instagram_account_repository.get_by_user_id(user_id)
        if account is None:
            raise InstagramAccountNotConnectedError("No Instagram account is connected for this user.")
        return account

    def _discover_instagram_account(self, user_access_token: str) -> tuple[str, str]:
        """Find the first Facebook Page with a linked Instagram Business account."""
        pages = self._call(self.instagram_client.get_facebook_pages, user_access_token=user_access_token)
        if not pages:
            raise InstagramOAuthError(
                "No Facebook Pages were found for this user. A Page linked to an "
                "Instagram Business or Creator account is required."
            )

        for page in pages:
            page_id = page.get("id")
            if not page_id:
                continue
            instagram_user_id = self._call(
                self.instagram_client.get_linked_instagram_account_id,
                page_id=page_id,
                access_token=user_access_token,
            )
            if instagram_user_id:
                return instagram_user_id, page_id

        raise InstagramOAuthError(
            "None of this user's Facebook Pages have a linked Instagram Business or Creator account."
        )

    def _upsert_media(self, instagram_account_id: int, item: dict[str, Any]) -> InstagramMedia:
        media_id = item["id"]
        posted_at = self._parse_timestamp(item.get("timestamp"))

        existing = self.instagram_media_repository.get_by_media_id(media_id)
        if existing is not None:
            existing.media_type = item.get("media_type", existing.media_type)
            existing.caption = item.get("caption")
            existing.media_url = item.get("media_url")
            existing.permalink = item.get("permalink")
            existing.posted_at = posted_at
            existing.like_count = item.get("like_count")
            existing.comments_count = item.get("comments_count")
            return existing

        return self.instagram_media_repository.create(
            InstagramMedia(
                instagram_account_id=instagram_account_id,
                media_id=media_id,
                media_type=item.get("media_type", "UNKNOWN"),
                caption=item.get("caption"),
                media_url=item.get("media_url"),
                permalink=item.get("permalink"),
                posted_at=posted_at,
                like_count=item.get("like_count"),
                comments_count=item.get("comments_count"),
            )
        )

    def _valid_access_token(self, account: InstagramAccount) -> str:
        expires_at = account.token_expires_at
        if expires_at is not None:
            # Stored as UTC; some backends (e.g. SQLite) drop tzinfo on
            # round-trip, so a naive value is always treated as UTC here.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise InstagramTokenExpiredError(
                    "The Instagram access token has expired. Please reconnect your account."
                )
        try:
            return decrypt_token(account.access_token)
        except ValueError as exc:
            raise InstagramServiceError(
                "Stored Instagram credentials could not be read. Please reconnect your account."
            ) from exc

    def _decode_state(self, state: str) -> int:
        try:
            return decode_oauth_state_token(state)
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise InvalidOAuthStateError("The OAuth state parameter is missing, invalid, or expired.") from exc

    def _call(self, func: Callable[..., T], **kwargs: Any) -> T:
        """Invoke a Graph API client call, translating failures into service exceptions."""
        try:
            return func(**kwargs)
        except InstagramAPIError as exc:
            if exc.status_code in (401, 403):
                raise InstagramTokenExpiredError(
                    "The Instagram access token is no longer valid. Please reconnect your account."
                ) from exc
            raise InstagramOAuthError(str(exc)) from exc

    def _commit(self) -> None:
        self.instagram_account_repository.db.commit()

    @staticmethod
    def _compute_expiry(expires_in: Any) -> datetime | None:
        if expires_in is None:
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    @staticmethod
    def _parse_timestamp(timestamp: str | None) -> datetime | None:
        """Parse a Graph API timestamp (e.g. '...+0000') into a datetime.

        Python's fromisoformat only accepts a colon-delimited UTC offset
        (e.g. '+00:00') until 3.11, while the Graph API returns '+0000', so
        the offset is normalized first for compatibility with older runtimes.
        """
        if not timestamp:
            return None
        normalized = timestamp
        if len(normalized) >= 5 and normalized[-5] in "+-" and normalized[-4:].isdigit():
            normalized = f"{normalized[:-2]}:{normalized[-2:]}"
        return datetime.fromisoformat(normalized)

    def _ensure_configured(self) -> None:
        if not (settings.INSTAGRAM_APP_ID and settings.INSTAGRAM_APP_SECRET and settings.INSTAGRAM_REDIRECT_URI):
            raise InstagramNotConfiguredError(
                "Instagram integration is not configured. Set INSTAGRAM_APP_ID, "
                "INSTAGRAM_APP_SECRET, and INSTAGRAM_REDIRECT_URI."
            )
