from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Provide common persistence operations for SQLAlchemy models."""

    def __init__(self, model: type[ModelType], db: Session) -> None:
        """Initialize the repository with a model class and database session."""
        self.model = model
        self.db = db

    def create(self, instance: ModelType) -> ModelType:
        """Add a model instance to the current transaction."""
        self.db.add(instance)
        self.db.flush()
        self.db.refresh(instance)
        return instance

    def get_by_id(self, record_id: int) -> ModelType | None:
        """Return a model instance by primary key, or None when missing."""
        return self.db.get(self.model, record_id)

    def get_all(self) -> list[ModelType]:
        """Return all rows for the repository model."""
        statement = select(self.model)
        return list(self.db.scalars(statement).all())

    def delete(self, record_id: int) -> bool:
        """Mark a row for deletion and return whether it existed."""
        instance = self.get_by_id(record_id)
        if instance is None:
            return False

        self.db.delete(instance)
        self.db.flush()
        return True
