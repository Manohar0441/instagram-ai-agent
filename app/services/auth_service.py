import jwt

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPayload
from app.utils.jwt import create_access_token, create_refresh_token, decode_refresh_token
from app.utils.security import verify_password


class AuthServiceError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials do not match a known user."""


class InvalidRefreshTokenError(AuthServiceError):
    """Raised when a refresh token is missing, expired, malformed, or
    belongs to a user that no longer exists."""


class AuthService:
    """Coordinate credential verification and access/refresh token issuance."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize the service with required repositories."""
        self.user_repository = user_repository

    def authenticate(self, email: str, password: str) -> User:
        """Return the user matching the given email and password."""
        user = self.user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password.")

        return user

    def login(self, email: str, password: str) -> tuple[str, str]:
        """Authenticate credentials and return (access_token, refresh_token)."""
        user = self.authenticate(email, password)
        return self._issue_tokens(user_id=user.id)

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        """Exchange a valid refresh token for a new (access_token, refresh_token)
        pair, without asking for credentials again.

        Re-issues both on every call (rather than reusing the presented
        refresh token) so a device used at least once every
        JWT_REFRESH_TOKEN_EXPIRE_DAYS stays signed in indefinitely - the
        session slides forward instead of hard-expiring on a fixed date.
        """
        try:
            payload = decode_refresh_token(refresh_token)
            token_data = TokenPayload(**payload)
            user_id = int(token_data.sub)
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidRefreshTokenError("Invalid or expired refresh token.") from exc

        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise InvalidRefreshTokenError("Invalid or expired refresh token.")

        return self._issue_tokens(user_id=user.id)

    @staticmethod
    def _issue_tokens(user_id: int) -> tuple[str, str]:
        subject = str(user_id)
        return create_access_token(subject=subject), create_refresh_token(subject=subject)
