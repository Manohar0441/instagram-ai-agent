from pydantic import BaseModel


class Token(BaseModel):
    """Access token returned after successful authentication."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Claims encoded in an access token."""

    sub: str
    exp: int
