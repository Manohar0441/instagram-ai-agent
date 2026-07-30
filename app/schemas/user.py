from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """Payload required to create a user."""

    username: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=200)


class UserResponse(BaseModel):
    """Public representation of a user."""

    id: int
    username: str
    full_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
