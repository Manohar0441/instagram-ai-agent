from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Handle persistence operations specific to users."""

    def __init__(self, db: Session) -> None:
        """Initialize the user repository."""
        super().__init__(User, db)

    def get_by_username(self, username: str) -> User | None:
        """Return a user by username, or None when no match exists."""
        statement = select(User).where(User.username == username)
        return self.db.scalar(statement)

    def get_by_email(self, email: str) -> User | None:
        """Return a user by email, or None when no match exists."""
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)
