from typing import Any
from urllib.parse import urlencode

import httpx

# Instagram API with Instagram Login (the current product; Meta's older
# Facebook-Login-based Instagram Graph API was superseded by this one in
# 2024 and stopped issuing its scopes to new apps). Token/auth endpoints are
# unversioned; data endpoints below are versioned per GRAPH_API_VERSION.
OAUTH_AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_LIVED_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"
GRAPH_API_BASE_URL = "https://graph.instagram.com"

# Read-only access to the connected account's own profile and insights.
# Publishing/messaging/comments scopes are not requested - this app never
# writes to Instagram.
OAUTH_SCOPES = "instagram_business_basic,instagram_business_manage_insights"

# The Graph API does not expose a "biography" field on this product (unlike
# the older Facebook-Login-based one), so it is not requested here; the
# corresponding column is always None for accounts connected this way.
PROFILE_FIELDS = "user_id,username,name,account_type,profile_picture_url,followers_count,media_count"
# like_count/comments_count are plain media fields (not insight metrics), so
# they're requested here rather than via the /insights edge.
MEDIA_FIELDS = "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count"

# Graph API insight metric names for Instagram API with Instagram Login.
# "impressions" was removed outright at the account level (no replacement
# metric - the impressions fields in app/schemas/analytics.py are always
# None as a result); "profile_views" was deprecated account-wide in Graph
# API v21 (Jan 2025) with no replacement either - profile_visits is always
# None as a result too (see AnalyticsService). "engagement" was renamed
# "total_interactions", and at the *media* level (not account) the save
# count is "saved", not "saves" - a request containing even one invalid
# metric name fails for the whole call, not just that metric, so keep these
# in sync with Meta's current allowed-metrics list if a sync starts failing
# with an "Invalid metric"/"metric[n] must be one of..." error.
ACCOUNT_INSIGHT_METRICS = "reach,accounts_engaged"
IMAGE_INSIGHT_METRICS = "reach,saved"
VIDEO_INSIGHT_METRICS = "views,reach,saved,shares"

# Reels watch-time metrics are even less stable across API versions than the
# core set above, so they're fetched as a separate best-effort call - see
# _get_watch_time_metrics.
VIDEO_WATCH_TIME_METRICS = "ig_reels_avg_watch_time"

REQUEST_TIMEOUT_SECONDS = 15.0


class InstagramAPIError(Exception):
    """Raised when a call to the Meta Graph API fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class InstagramGraphClient:
    """Thin wrapper around the Instagram API endpoints this app needs.

    New Graph API calls should be added here as additional methods so the
    service layer never constructs Graph API URLs or parses raw responses
    itself.
    """

    def __init__(self, app_id: str, app_secret: str, api_version: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.api_version = api_version

    def build_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Build the Instagram Login consent screen URL."""
        params = {
            "client_id": self.app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": OAUTH_SCOPES,
            "response_type": "code",
        }
        return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_user_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an OAuth authorization code for a short-lived user access token.

        Unlike the other calls here, this one is a POST with a form-encoded
        body - that's how Instagram's token endpoint expects it, not query
        parameters.
        """
        return self._post(
            SHORT_LIVED_TOKEN_URL,
            data={
                "client_id": self.app_id,
                "client_secret": self.app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )

    def exchange_for_long_lived_token(self, short_lived_token: str) -> dict[str, Any]:
        """Exchange a short-lived user token for a long-lived (~60 day) one."""
        return self._get(
            LONG_LIVED_TOKEN_URL,
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": self.app_secret,
                "access_token": short_lived_token,
            },
        )

    def get_profile(self, access_token: str) -> dict[str, Any]:
        """Fetch profile/account information for the token's own Instagram account.

        Instagram Login tokens are scoped to exactly one account, so this
        always reads via /me rather than by ID - it doubles as account
        discovery right after connecting (the response's user_id is the
        account to store) and as the later profile-refresh call.
        """
        return self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/me",
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
        is_video = media_type in ("VIDEO", "REELS")
        metrics = VIDEO_INSIGHT_METRICS if is_video else IMAGE_INSIGHT_METRICS
        response = self._get(
            f"{GRAPH_API_BASE_URL}/{self.api_version}/{media_id}/insights",
            params={"metric": metrics, "access_token": access_token},
        )
        result = self._flatten_insight_values(response.get("data", []))

        if is_video:
            result.update(self._get_watch_time_metrics(media_id, access_token))

        return result

    def _get_watch_time_metrics(self, media_id: str, access_token: str) -> dict[str, Any]:
        """Best-effort fetch for Reels watch-time metrics.

        These metric names are less stable across Graph API versions than
        the core set, so a failure here is swallowed rather than propagated
        - the caller simply won't have watch-time data for this item.
        """
        try:
            response = self._get(
                f"{GRAPH_API_BASE_URL}/{self.api_version}/{media_id}/insights",
                params={"metric": VIDEO_WATCH_TIME_METRICS, "access_token": access_token},
            )
        except InstagramAPIError:
            return {}
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
        return self._parse(response)

    def _post(self, url: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(url, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
        except httpx.RequestError as exc:
            raise InstagramAPIError(f"Failed to reach Instagram API: {exc}") from exc
        return self._parse(response)

    def _parse(self, response: httpx.Response) -> dict[str, Any]:
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
