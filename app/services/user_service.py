from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate


class UserServiceError(Exception):
    """Base exception for user service failures."""


class DuplicateUsernameError(UserServiceError):
    """Raised when attempting to create a user with an existing username."""


class UserNotFoundError(UserServiceError):
    """Raised when a requested user does not exist."""


class UserService:
    """Coordinate user business rules and persistence."""

    def __init__(self, user_repository: UserRepository) -> None:
        """Initialize the service with required repositories."""
        self.user_repository = user_repository

    def create_user(self, user_data: UserCreate) -> User:
        """Create a user after enforcing username uniqueness."""
        existing_user = self.user_repository.get_by_username(user_data.username)
        if existing_user is not None:
            raise DuplicateUsernameError(
                f"Username '{user_data.username}' is already in use."
            )

        user = User(
            username=user_data.username,
            full_name=user_data.full_name,
        )

        try:
            created_user = self.user_repository.create(user)
            self._commit()
            return created_user
        except IntegrityError as exc:
            self._rollback()
            if self._is_unique_constraint_error(exc):
                raise DuplicateUsernameError(
                    f"Username '{user_data.username}' is already in use."
                ) from exc
            raise UserServiceError("Failed to create user.") from exc
        except SQLAlchemyError as exc:
            self._rollback()
            raise UserServiceError("Failed to create user.") from exc

    def get_user(self, user_id: int) -> User:
        """Return a user by ID or raise when not found."""
        user = self.user_repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} was not found.")

        return user

    def list_users(self) -> list[User]:
        """Return all users."""
        return self.user_repository.get_all()

    def _commit(self) -> None:
        """Commit the current database transaction."""
        self.user_repository.db.commit()

    def _rollback(self) -> None:
        """Rollback the current database transaction."""
        self.user_repository.db.rollback()

    @staticmethod
    def _is_unique_constraint_error(exc: IntegrityError) -> bool:
        """Return whether an integrity error came from a unique constraint."""
        return getattr(exc.orig, "pgcode", None) == "23505"
