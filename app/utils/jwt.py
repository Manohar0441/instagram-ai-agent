from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.settings import settings


# Every token this app issues carries a "type" claim identifying what it may
# be used for, and each decoder verifies it. Without this, any token signed
# with JWT_SECRET_KEY is interchangeable with any other - in particular an
# OAuth state token (which travels in a URL, and so ends up in browser
# history, address bars, and Referer headers sent to facebook.com) would be
# accepted as an API access token.
_ACCESS_TOKEN_TYPE = "access"
_REFRESH_TOKEN_TYPE = "refresh"
_OAUTH_STATE_TOKEN_TYPE = "instagram_oauth_state"
_OAUTH_STATE_EXPIRE_MINUTES = 10


def create_access_token(subject: str) -> str:
    """Create a signed JWT access token for the given subject."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expires_at, "type": _ACCESS_TOKEN_TYPE}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises jwt.PyJWTError (including for a mismatched token type) on failure.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != _ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Token is not a valid access token.")
    return payload


def create_refresh_token(subject: str) -> str:
    """Create a signed, long-lived JWT refresh token for the given subject.

    Stateless like every other token here - there is no server-side session
    store to revoke it against. /auth/refresh re-issues a fresh refresh
    token (and access token) on every successful use, so a device that's
    used at least once every JWT_REFRESH_TOKEN_EXPIRE_DAYS stays signed in
    indefinitely; one that isn't falls back to a normal login.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": subject, "exp": expires_at, "type": _REFRESH_TOKEN_TYPE}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT refresh token.

    Raises jwt.PyJWTError (including for a mismatched token type, which is
    what stops an access token from being replayed here) on failure.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != _REFRESH_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Token is not a valid refresh token.")
    return payload


def create_oauth_state_token(user_id: int) -> str:
    """Create a short-lived signed token binding an OAuth round-trip to a user."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=_OAUTH_STATE_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expires_at, "type": _OAUTH_STATE_TOKEN_TYPE}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_oauth_state_token(token: str) -> int:
    """Decode an OAuth state token and return the bound user ID.

    Raises jwt.PyJWTError (including for a mismatched token type) on failure.
    """
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != _OAUTH_STATE_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Token is not a valid OAuth state token.")
    return int(payload["sub"])
