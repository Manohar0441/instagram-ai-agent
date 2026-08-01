from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.settings import settings
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_instagram_service
from app.models.user import User
from app.schemas.instagram import (
    AccountInsightResponse,
    InstagramAccountResponse,
    InstagramConnectResponse,
    InstagramMediaResponse,
    InsightsResponse,
    MediaInsightResponse,
)
from app.services.instagram_service import (
    DuplicateInstagramAccountError,
    InstagramAccountAlreadyConnectedError,
    InstagramAccountNotConnectedError,
    InstagramNotConfiguredError,
    InstagramOAuthError,
    InstagramService,
    InstagramServiceError,
    InstagramTokenExpiredError,
    InvalidOAuthStateError,
)

router = APIRouter(prefix="/instagram", tags=["Instagram"])

InstagramServiceDependency = Annotated[InstagramService, Depends(get_instagram_service)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _handle_service_error(exc: InstagramServiceError) -> HTTPException:
    """Translate an Instagram service exception into the matching HTTP response."""
    if isinstance(exc, InstagramNotConfiguredError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, InvalidOAuthStateError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, InstagramAccountNotConnectedError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (InstagramAccountAlreadyConnectedError, DuplicateInstagramAccountError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InstagramTokenExpiredError):
        return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, InstagramOAuthError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# Where in the frontend the OAuth round-trip lands.
_FRONTEND_CALLBACK_PATH = "/onboarding/instagram"


def _callback_error_code(exc: InstagramServiceError) -> str:
    """Map an Instagram service exception to a stable frontend-facing code.

    The frontend renders its own copy from these rather than displaying a
    backend string, so they are part of the contract and must stay stable.
    Ordered most-specific first, mirroring _handle_service_error.
    """
    if isinstance(exc, InstagramNotConfiguredError):
        return "not_configured"
    if isinstance(exc, InvalidOAuthStateError):
        return "invalid_state"
    if isinstance(exc, (InstagramAccountAlreadyConnectedError, DuplicateInstagramAccountError)):
        return "already_connected"
    if isinstance(exc, InstagramTokenExpiredError):
        return "token_expired"
    if isinstance(exc, InstagramOAuthError):
        return "provider_error"
    return "unknown_error"


def _frontend_redirect(
    result: str,
    code: str | None = None,
    message: str | None = None,
) -> RedirectResponse:
    """Send the browser back to the frontend with the outcome of the OAuth trip.

    The target is built from FRONTEND_URL, which is server configuration
    and never request input, so this cannot become an open redirect. The
    message is a service exception string - these are written for display
    and never interpolate a token, which matters because this URL lands in
    the user's browser history.
    """
    params = {"status": result}
    if code:
        params["code"] = code
    if message:
        params["message"] = message

    base = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(
        url=f"{base}{_FRONTEND_CALLBACK_PATH}?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )


@router.get(
    "/connect",
    response_model=InstagramConnectResponse,
    status_code=status.HTTP_200_OK,
    summary="Start Instagram connection",
    description=(
        "Return the Meta consent screen URL to start connecting an Instagram "
        "Business/Creator account. The client is responsible for navigating "
        "the browser to authorization_url; this endpoint does not redirect."
    ),
    operation_id="connectInstagram",
    responses={
        status.HTTP_200_OK: {"description": "Authorization URL generated successfully."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Instagram integration is not configured."},
    },
)
def connect(
    current_user: CurrentUser,
    instagram_service: InstagramServiceDependency,
) -> InstagramConnectResponse:
    """Generate the OAuth authorization URL for the current user."""
    try:
        authorization_url = instagram_service.get_authorization_url(current_user.id)
        return InstagramConnectResponse(authorization_url=authorization_url)
    except InstagramServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/callback",
    response_class=RedirectResponse,
    status_code=status.HTTP_302_FOUND,
    summary="Handle Instagram OAuth callback",
    description=(
        "Handle Meta's OAuth redirect: exchange the authorization code for "
        "tokens, persist the connected account, and redirect the browser "
        "back to the frontend with the outcome. Not Bearer-protected — the "
        "signed 'state' parameter identifies the initiating user, since "
        "browser redirects cannot carry an Authorization header."
    ),
    operation_id="instagramOAuthCallback",
    responses={
        status.HTTP_302_FOUND: {
            "description": (
                "Redirect to the frontend carrying 'status' (connected or "
                "error) and, on failure, a stable 'code' and a 'message'."
            )
        },
    },
)
def callback(
    instagram_service: InstagramServiceDependency,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """Exchange the OAuth code for tokens, then redirect back to the frontend.

    Every outcome is a redirect rather than a status code: this endpoint is
    reached by a browser navigation from Meta, so an error response would
    strand the user on a JSON page with no way back into the app.
    """
    if error:
        return _frontend_redirect(
            "error",
            code="access_denied",
            message=error_description or f"Instagram authorization failed: {error}",
        )
    if not code or not state:
        return _frontend_redirect(
            "error",
            code="missing_parameters",
            message="Missing required 'code' or 'state' query parameter.",
        )

    try:
        instagram_service.connect_account(code=code, state=state)
    except InstagramServiceError as exc:
        return _frontend_redirect("error", code=_callback_error_code(exc), message=str(exc))

    return _frontend_redirect("connected")


@router.get(
    "/profile",
    response_model=InstagramAccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get connected Instagram profile",
    description="Refresh and return the connected Instagram account's profile information.",
    operation_id="getInstagramProfile",
    responses={
        status.HTTP_200_OK: {"description": "Profile returned successfully."},
        status.HTTP_401_UNAUTHORIZED: {"description": "The access token has expired or been revoked."},
        status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
        status.HTTP_502_BAD_GATEWAY: {"description": "The Instagram API request failed."},
    },
)
def get_profile(
    current_user: CurrentUser,
    instagram_service: InstagramServiceDependency,
) -> InstagramAccountResponse:
    """Return the current user's connected Instagram profile."""
    try:
        account = instagram_service.get_profile(current_user.id)
        return InstagramAccountResponse.model_validate(account)
    except InstagramServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/media",
    response_model=list[InstagramMediaResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Instagram media",
    description="Fetch recent posts and reels from Instagram and store them.",
    operation_id="getInstagramMedia",
    responses={
        status.HTTP_200_OK: {"description": "Media returned successfully."},
        status.HTTP_401_UNAUTHORIZED: {"description": "The access token has expired or been revoked."},
        status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
        status.HTTP_502_BAD_GATEWAY: {"description": "The Instagram API request failed."},
    },
)
def get_media(
    current_user: CurrentUser,
    instagram_service: InstagramServiceDependency,
    limit: Annotated[int, Query(gt=0, le=100)] = 25,
) -> list[InstagramMediaResponse]:
    """Return the current user's fetched Instagram media."""
    try:
        media = instagram_service.get_media(current_user.id, limit=limit)
        return [InstagramMediaResponse.model_validate(item) for item in media]
    except InstagramServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.get(
    "/insights",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Instagram insights",
    description=(
        "Fetch and store account-level insights, plus insights for each "
        "already-fetched media item (call GET /instagram/media first to "
        "populate media)."
    ),
    operation_id="getInstagramInsights",
    responses={
        status.HTTP_200_OK: {"description": "Insights returned successfully."},
        status.HTTP_401_UNAUTHORIZED: {"description": "The access token has expired or been revoked."},
        status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
        status.HTTP_502_BAD_GATEWAY: {"description": "The Instagram API request failed."},
    },
)
def get_insights(
    current_user: CurrentUser,
    instagram_service: InstagramServiceDependency,
) -> InsightsResponse:
    """Return freshly fetched account and media insight snapshots."""
    try:
        account_insight, media_insight_pairs = instagram_service.get_insights(current_user.id)
        return InsightsResponse(
            account_insights=AccountInsightResponse.model_validate(account_insight),
            media_insights=[
                MediaInsightResponse(
                    media_id=media.media_id,
                    metrics=insight.metrics,
                    fetched_at=insight.fetched_at,
                )
                for media, insight in media_insight_pairs
            ],
        )
    except InstagramServiceError as exc:
        raise _handle_service_error(exc) from exc


@router.delete(
    "/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Instagram account",
    description="Disconnect the current user's Instagram account and remove stored credentials and data.",
    operation_id="disconnectInstagram",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Instagram account disconnected successfully."},
        status.HTTP_404_NOT_FOUND: {"description": "No Instagram account is connected."},
    },
)
def disconnect(
    current_user: CurrentUser,
    instagram_service: InstagramServiceDependency,
) -> None:
    """Disconnect the current user's Instagram account."""
    try:
        instagram_service.disconnect_account(current_user.id)
    except InstagramServiceError as exc:
        raise _handle_service_error(exc) from exc
