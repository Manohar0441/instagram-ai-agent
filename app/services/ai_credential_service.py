from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from app.core.settings import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.ai import AIKeyStatusResponse
from app.services.ai_generation import (
    AIGenerationError,
    AIKeyRejectedError,
    AINotConfiguredError,
    verify_api_key,
)
from app.utils.encryption import decrypt_token, encrypt_token

# Only the tail of a key is ever shown back to a user, so they can tell
# which key is stored without the value being recoverable from the API.
_HINT_LENGTH = 4


class AIUserNotFoundError(AIGenerationError):
    """Raised when the user a credential operation targets does not exist."""


class AICredentialService:
    """Resolve and manage each user's Gemini API key.

    Owns the single resolution rule used by every AI-backed code path -
    the request handlers and the background report worker alike - so the
    precedence (the user's own key, then the server-wide development
    fallback, then failure) can only ever be changed in one place.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize the service with required repositories."""
        self.user_repository = user_repository

    def resolve_api_key(self, user_id: int) -> str:
        """Return the Gemini API key to use for a user, or raise when there is none.

        Order: the user's own stored key, then settings.GOOGLE_API_KEY as a
        development fallback, then AINotConfiguredError.
        """
        user = self.user_repository.get_by_id(user_id)

        if user is not None and user.gemini_api_key:
            try:
                return decrypt_token(user.gemini_api_key)
            except ValueError as exc:
                # TOKEN_ENCRYPTION_KEY was rotated after this key was
                # stored. Falling through to the server key would silently
                # bill the wrong account, so this is a hard stop that the
                # user can clear by entering their key again.
                raise AINotConfiguredError(
                    "Your stored Gemini API key could not be decrypted. "
                    "Please enter it again in Settings."
                ) from exc

        if settings.GOOGLE_API_KEY:
            return settings.GOOGLE_API_KEY

        raise AINotConfiguredError(
            "AI features are not configured. Add a Gemini API key in Settings."
        )

    def get_status(self, user_id: int) -> AIKeyStatusResponse:
        """Report whether a Gemini API key is available for a user.

        Never includes the key itself, only where it came from and a short
        hint drawn from its final characters.
        """
        user = self.user_repository.get_by_id(user_id)
        stored = user.gemini_api_key if user is not None else None

        source: Literal["user", "server", "none"]
        if stored:
            source = "user"
        elif settings.GOOGLE_API_KEY:
            source = "server"
        else:
            source = "none"

        return AIKeyStatusResponse(
            configured=source != "none",
            has_own_key=bool(stored),
            source=source,
            hint=self._hint(stored),
            model=settings.GEMINI_MODEL,
        )

    def set_api_key(self, user_id: int, plain_key: str) -> AIKeyStatusResponse:
        """Validate and store a user's Gemini API key, replacing any existing one."""
        user = self._get_user(user_id)
        verify_api_key(plain_key)

        try:
            self.user_repository.set_gemini_api_key(user, encrypt_token(plain_key))
            self._commit()
        except SQLAlchemyError as exc:
            self._rollback()
            raise AIGenerationError("Failed to save the Gemini API key.") from exc

        return self.get_status(user_id)

    def clear_api_key(self, user_id: int) -> None:
        """Remove a user's stored Gemini API key."""
        user = self._get_user(user_id)

        try:
            self.user_repository.set_gemini_api_key(user, None)
            self._commit()
        except SQLAlchemyError as exc:
            self._rollback()
            raise AIGenerationError("Failed to remove the Gemini API key.") from exc

    def _get_user(self, user_id: int) -> User:
        """Return a user by ID, or raise when the record no longer exists."""
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise AIUserNotFoundError(f"User with ID {user_id} was not found.")

        return user

    def _commit(self) -> None:
        """Commit the current database transaction."""
        self.user_repository.db.commit()

    def _rollback(self) -> None:
        """Rollback the current database transaction."""
        self.user_repository.db.rollback()

    @staticmethod
    def _hint(encrypted_key: str | None) -> str | None:
        """Return the last few characters of a stored key, or None when unset."""
        if not encrypted_key:
            return None

        try:
            return decrypt_token(encrypted_key)[-_HINT_LENGTH:]
        except ValueError:
            # An unreadable key is reported as having no hint rather than
            # failing the whole status call - resolve_api_key is where that
            # becomes an error the user has to act on.
            return None


# Re-exported so routers can translate key failures without reaching into
# ai_generation for exceptions this service is the one that raises.
__all__ = [
    "AICredentialService",
    "AIKeyRejectedError",
    "AINotConfiguredError",
    "AIUserNotFoundError",
]
