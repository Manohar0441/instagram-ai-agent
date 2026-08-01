from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """A natural language query for the AI analytics agent."""

    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """The agent's answer, along with which analytics tools informed it."""

    response: str
    tools_used: list[str]


class AIHealthResponse(BaseModel):
    """Configuration/readiness status of the AI service and its dependencies."""

    status: Literal["ok", "unavailable"]
    model: str
    configured: bool
    details: str | None = None


class AIKeyUpdateRequest(BaseModel):
    """A user-supplied Gemini API key to store."""

    # The pattern rejects whitespace-padded pastes and anything URL-shaped.
    # It also keeps malformed values out of the ValidationError detail,
    # which is returned to the client.
    api_key: str = Field(min_length=20, max_length=200, pattern=r"^[A-Za-z0-9_\-.]+$")


class AIKeyStatusResponse(BaseModel):
    """Whether a Gemini API key is available for a user.

    Never contains the key itself - only whether one is usable, where it
    came from, and enough of a hint to tell two keys apart.
    """

    configured: bool
    has_own_key: bool
    source: Literal["user", "server", "none"]
    hint: str | None = None
    model: str
