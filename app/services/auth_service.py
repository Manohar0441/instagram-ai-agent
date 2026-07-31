from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.utils.jwt import create_access_token
from app.utils.security import verify_password


class AuthServiceError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials do not match a known user."""


class AuthService:
    """Coordinate credential verification and access token issuance."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize the service with required repositories."""
        self.user_repository = user_repository

    def authenticate(self, email: str, password: str) -> User:
        """Return the user matching the given email and password."""
        user = self.user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password.")

        return user

    def login(self, email: str, password: str) -> str:
        """Authenticate credentials and return a signed access token."""
        user = self.authenticate(email, password)
        return create_access_token(subject=str(user.id))
