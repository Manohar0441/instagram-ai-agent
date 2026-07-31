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
    openai_configured: bool
    details: str | None = None
