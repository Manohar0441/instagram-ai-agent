from pydantic import BaseModel


class Token(BaseModel):
    """Access + refresh token pair returned after successful authentication
    or a refresh - the refresh token is what keeps a device signed in
    without asking for credentials again."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Body of a POST /auth/refresh call."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Claims encoded in an access token."""

    sub: str
    exp: int
