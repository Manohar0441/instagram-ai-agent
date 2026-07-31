from typing import Any
from urllib.parse import urlencode

import httpx

OAUTH_DIALOG_BASE_URL = "https://www.facebook.com"
GRAPH_API_BASE_URL = "https://graph.facebook.com"

# Facebook Login for Business permissions required to discover a user's
# Pages and read their linked Instagram Business/Creator account.
OAUTH_SCOPES = "instagram_basic,instagram_manage_insights,pages_show_list,pages_read_engagement"

PROFILE_FIELDS = "id,username,name,account_type,profile_picture_url,followers_count,media_count,biography"
MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,timestamp"

# Graph API insight metric names as documented for API version v21.x. Meta
# periodically renames/deprecates metrics between API versions; if calls
# start failing with an "Invalid metric" error, these lists are the first
# place to check against the pinned INSTAGRAM_GRAPH_API_VERSION.
ACCOUNT_INSIGHT_METRICS = "impressions,reach,profile_views"
IMAGE_INSIGHT_METRICS = "impressions,reach,engagement,saved"
VIDEO_INSIGHT_METRICS = "plays,reach,saved,shares"

REQUEST_TIMEOUT_SECONDS = 15.0


class InstagramAPIError(Exception):
    """Raised when a call to the Meta Graph API fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InstagramGraphClient:
    """Thin wrapper around the Meta Graph API endpoints this app needs.

    New Graph API calls should be added here as additional methods so the
    service layer never constructs Graph API URLs or parses raw responses
    itself.
    """

    def __init__(self, app_id: str, app_secret: str, api_version: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_version = api_version

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Build the Facebook Login for Business consent screen URL."""
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": OAUTH_SCOPES,
            "response_type": "code",
        }
        return f"{OAUTH_DIALOG_BASE_URL}/{self.api_version}/dialog/oauth?{urlencode(params)}"

    def exchange_code_for_user_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an OAuth authorization code for a short-lived user access token."""
        return self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/oauth/access_token",
            params={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )

    def exchange_for_long_lived_token(self, short_lived_token: str) -> dict[str, Any]:
        """Exchange a short-lived user token for a long-lived (~60 day) one."""
        return self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "fb_exchange_token": short_lived_token,
            },
        )

    def get_facebook_pages(self, user_access_token: str) -> list[dict[str, Any]]:
        """Return the Facebook Pages managed by the authenticated user."""
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/me/accounts",
            params={"access_token": user_access_token},
        )
        return response.get("data", [])

    def get_linked_instagram_account_id(self, page_id: str, access_token: str) -> str | None:
        """Return the Instagram Business Account ID linked to a Facebook Page, if any."""
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{page_id}",
            params={"fields": "instagram_business_account", "access_token": access_token},
        )
        instagram_account = response.get("instagram_business_account")
        return instagram_account["id"] if instagram_account else None

    def get_profile(self, instagram_user_id: str, access_token: str) -> dict[str, Any]:
        """Fetch profile/account information for the connected Instagram account."""
        return self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{instagram_user_id}",
            params={"fields": PROFILE_FIELDS, "access_token": access_token},
        )

    def get_media(
        self,
        instagram_user_id: str,
        access_token: str,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Fetch recent posts and reels for the connected Instagram account."""
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{instagram_user_id}/media",
            params={"fields": MEDIA_FIELDS, "limit": limit, "access_token": access_token},
        )
        return response.get("data", [])

    def get_media_insights(
        self,
        media_id: str,
        media_type: str,
        access_token: str,
    ) -> dict[str, Any]:
        """Fetch insight metrics for a single media item."""
        metrics = VIDEO_INSIGHT_METRICS if media_type in ("VIDEO", "REELS") else IMAGE_INSIGHT_METRICS
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{media_id}/insights",
            params={"metric": metrics, "access_token": access_token},
        )
        return self._flatten_insight_values(response.get("data", []))

    def get_account_insights(
        self,
        instagram_user_id: str,
        access_token: str,
        period: str = "day",
    ) -> dict[str, Any]:
        """Fetch account-level insight metrics for the given period."""
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{instagram_user_id}/insights",
            params={"metric": ACCOUNT_INSIGHT_METRICS, "period": period, "access_token": access_token},
        )
        return self._flatten_insight_values(response.get("data", []))

    @staticmethod
    def _flatten_insight_values(insight_entries: list[dict[str, Any]]) -> dict[str, Any]:
        """Reduce the Graph API's verbose insights format to {metric_name: value}."""
        metrics: dict[str, Any] = {}
        for entry in insight_entries:
            name = entry.get("name")
            values = entry.get("values", [])
            if name and values:
                metrics[name] = values[-1].get("value")
        return metrics

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except httpx.RequestError as exc:
            raise InstagramAPIError(f"Failed to reach Instagram API: {exc}") from exc

        body = self._safe_json(response)

        if response.is_error:
            message = self._extract_error_message(body, response)
            raise InstagramAPIError(message, status_code=response.status_code)

        return body

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {}

    @staticmethod
    def _extract_error_message(body: dict[str, Any], response: httpx.Response) -> str:
        error = body.get("error", {})
        return error.get("message") or f"Instagram API request failed with status {response.status_code}."
