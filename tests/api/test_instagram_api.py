from urllib.parse import parse_qs, urlparse

import pytest

from app.dependencies.services import get_instagram_client
from app.main import app

pytestmark = pytest.mark.api


@pytest.fixture
def instagram_client(client, fake_graph_client, monkeypatch):
    """A TestClient whose Instagram integration is configured and stubbed."""
    from app.core.settings import settings

    monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", "test-app-id")
    monkeypatch.setattr(settings, "INSTAGRAM_APP_SECRET", "test-app-secret")
    monkeypatch.setattr(
        settings, "INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/v1/instagram/callback"
    )
    app.dependency_overrides[get_instagram_client] = lambda: fake_graph_client
    yield client
    app.dependency_overrides.pop(get_instagram_client, None)


def start_oauth(instagram_client, auth_headers) -> str:
    """Run /connect and pull the signed state parameter out of the URL."""
    response = instagram_client.get("/api/v1/instagram/connect", headers=auth_headers)
    url = response.json()["authorization_url"]
    return parse_qs(urlparse(url).query)["state"][0]


def finish_oauth(instagram_client, query: str):
    """Call the OAuth callback without chasing its redirect.

    The callback now answers with a 302 to the frontend, and TestClient
    follows redirects by default - which would try to reach the real
    frontend origin and fail with a connection error.
    """
    return instagram_client.get(
        f"/api/v1/instagram/callback?{query}", follow_redirects=False
    )


def callback_params(response) -> dict[str, str]:
    """Parse the frontend redirect a callback response points at."""
    location = response.headers["location"]
    return {key: value[0] for key, value in parse_qs(urlparse(location).query).items()}


class TestConnect:
    def test_returns_an_authorization_url(self, instagram_client, auth_headers):
        response = instagram_client.get("/api/v1/instagram/connect", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["authorization_url"].startswith("https://www.instagram.com/")

    def test_reports_503_when_not_configured(
        self, instagram_client, auth_headers, monkeypatch
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", None)
        response = instagram_client.get("/api/v1/instagram/connect", headers=auth_headers)
        assert response.status_code == 503


class TestCallback:
    """The callback is reached by a browser redirect from Meta, so every
    outcome is a 302 back to the frontend carrying a stable status/code
    rather than an HTTP error the user would be stranded on.
    """

    def test_completes_the_connection(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        response = finish_oauth(instagram_client, f"code=auth-code&state={state}")

        assert response.status_code == 302
        assert response.headers["location"].startswith(
            "http://localhost:3000/onboarding/instagram"
        )
        assert callback_params(response)["status"] == "connected"

        # The redirect carries no data, so prove the account was actually
        # persisted rather than merely reported.
        profile = instagram_client.get("/api/v1/instagram/profile", headers=auth_headers)
        assert profile.status_code == 200
        assert profile.json()["username"] == "test_creator"

    def test_never_exposes_the_access_token_or_page_id(
        self, instagram_client, auth_headers
    ):
        """A redirect URL is a worse leak channel than a response body - it
        lands in browser history and can travel in a Referer header."""
        state = start_oauth(instagram_client, auth_headers)
        location = finish_oauth(
            instagram_client, f"code=auth-code&state={state}"
        ).headers["location"]

        assert "long_lived_token" not in location
        assert "fb_page_1" not in location
        assert "access_token" not in location

    def test_works_without_an_authorization_header(self, instagram_client, auth_headers):
        """Meta redirects the browser here, so no bearer token can be
        attached; the signed state parameter identifies the user instead."""
        state = start_oauth(instagram_client, auth_headers)
        response = finish_oauth(instagram_client, f"code=auth-code&state={state}")

        assert response.status_code == 302
        assert callback_params(response)["status"] == "connected"

    def test_redirects_to_the_configured_frontend(
        self, instagram_client, auth_headers, monkeypatch
    ):
        """FRONTEND_URL is the single source of the redirect target."""
        from app.core.settings import settings

        monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com/")
        state = start_oauth(instagram_client, auth_headers)
        response = finish_oauth(instagram_client, f"code=auth-code&state={state}")

        assert response.headers["location"].startswith(
            "https://app.example.com/onboarding/instagram"
        )

    def test_rejects_a_forged_state(self, instagram_client, auth_headers):
        response = finish_oauth(instagram_client, "code=auth-code&state=forged")

        params = callback_params(response)
        assert params["status"] == "error"
        assert params["code"] == "invalid_state"

    def test_rejects_an_access_token_used_as_state(self, instagram_client, auth_headers):
        """The inverse of the access-token confusion check."""
        token = auth_headers["Authorization"].removeprefix("Bearer ")
        response = finish_oauth(instagram_client, f"code=auth-code&state={token}")

        assert callback_params(response)["code"] == "invalid_state"

    def test_surfaces_a_user_denial(self, instagram_client):
        response = finish_oauth(
            instagram_client, "error=access_denied&error_description=User+denied"
        )

        params = callback_params(response)
        assert params["status"] == "error"
        assert params["code"] == "access_denied"

    def test_requires_code_and_state(self, instagram_client):
        response = finish_oauth(instagram_client, "")

        assert callback_params(response)["code"] == "missing_parameters"

    def test_rejects_a_second_connection(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        finish_oauth(instagram_client, f"code=auth-code&state={state}")

        second_state = start_oauth(instagram_client, auth_headers)
        response = finish_oauth(instagram_client, f"code=auth-code&state={second_state}")

        assert callback_params(response)["code"] == "already_connected"


class TestConnectedEndpoints:
    @pytest.fixture
    def connected(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        response = finish_oauth(instagram_client, f"code=auth-code&state={state}")
        # Assert rather than ignore: if connecting silently stops working,
        # every test using this fixture should say so directly instead of
        # failing later for an apparently unrelated reason.
        assert callback_params(response)["status"] == "connected"
        return instagram_client

    def test_profile_returns_the_connected_account(self, connected, auth_headers):
        response = connected.get("/api/v1/instagram/profile", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["username"] == "test_creator"

    def test_profile_is_404_before_connecting(self, instagram_client, auth_headers):
        response = instagram_client.get("/api/v1/instagram/profile", headers=auth_headers)
        assert response.status_code == 404

    def test_media_returns_fetched_items(self, connected, auth_headers):
        response = connected.get("/api/v1/instagram/media", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_insights_returns_account_and_media_metrics(self, connected, auth_headers):
        connected.get("/api/v1/instagram/media", headers=auth_headers)
        response = connected.get("/api/v1/instagram/insights", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["account_insights"]["metrics"]["reach"] == 4000
        assert len(response.json()["media_insights"]) == 2

    def test_disconnect_removes_the_connection(self, connected, auth_headers):
        assert connected.delete(
            "/api/v1/instagram/disconnect", headers=auth_headers
        ).status_code == 204
        assert connected.get(
            "/api/v1/instagram/profile", headers=auth_headers
        ).status_code == 404

    def test_disconnect_without_a_connection_is_404(self, instagram_client, auth_headers):
        response = instagram_client.delete(
            "/api/v1/instagram/disconnect", headers=auth_headers
        )
        assert response.status_code == 404
