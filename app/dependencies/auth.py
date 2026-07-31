from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.dependencies.repositories import get_user_repository
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPayload
from app.utils.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _credentials_exception() -> HTTPException:
    """Build the standard 401 response for invalid or missing credentials."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Resolve the authenticated user from a bearer JWT access token."""
    try:
        payload = decode_access_token(token)
        token_data = TokenPayload(**payload)
        # int() is inside the try deliberately: a token with a well-formed
        # but non-numeric "sub" is an invalid credential (401), not an
        # internal error (500).
        user_id = int(token_data.sub)
    except (jwt.PyJWTError, ValueError) as exc:
        raise _credentials_exception() from exc

    user = user_repository.get_by_id(user_id)
    if user is None:
        raise _credentials_exception()

    return user
