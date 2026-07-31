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


class TestConnect:
    def test_returns_an_authorization_url(self, instagram_client, auth_headers):
        response = instagram_client.get("/api/v1/instagram/connect", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["authorization_url"].startswith("https://www.facebook.com/")

    def test_reports_503_when_not_configured(
        self, instagram_client, auth_headers, monkeypatch
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "INSTAGRAM_APP_ID", None)
        response = instagram_client.get("/api/v1/instagram/connect", headers=auth_headers)
        assert response.status_code == 503


class TestCallback:
    def test_completes_the_connection(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        response = instagram_client.get(
            f"/api/v1/instagram/callback?code=auth-code&state={state}"
        )
        assert response.status_code == 200
        assert response.json()["username"] == "test_creator"

    def test_never_exposes_the_access_token_or_page_id(
        self, instagram_client, auth_headers
    ):
        state = start_oauth(instagram_client, auth_headers)
        body = instagram_client.get(
            f"/api/v1/instagram/callback?code=auth-code&state={state}"
        ).json()
        assert "access_token" not in body
        assert "facebook_page_id" not in body

    def test_works_without_an_authorization_header(self, instagram_client, auth_headers):
        """Meta redirects the browser here, so no bearer token can be
        attached; the signed state parameter identifies the user instead."""
        state = start_oauth(instagram_client, auth_headers)
        response = instagram_client.get(
            f"/api/v1/instagram/callback?code=auth-code&state={state}"
        )
        assert response.status_code == 200

    def test_rejects_a_forged_state(self, instagram_client, auth_headers):
        response = instagram_client.get(
            "/api/v1/instagram/callback?code=auth-code&state=forged"
        )
        assert response.status_code == 401

    def test_rejects_an_access_token_used_as_state(self, instagram_client, auth_headers):
        """The inverse of the access-token confusion check."""
        token = auth_headers["Authorization"].removeprefix("Bearer ")
        response = instagram_client.get(
            f"/api/v1/instagram/callback?code=auth-code&state={token}"
        )
        assert response.status_code == 401

    def test_surfaces_a_user_denial(self, instagram_client):
        response = instagram_client.get(
            "/api/v1/instagram/callback?error=access_denied&error_description=User+denied"
        )
        assert response.status_code == 400

    def test_requires_code_and_state(self, instagram_client):
        assert instagram_client.get("/api/v1/instagram/callback").status_code == 400

    def test_rejects_a_second_connection(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        instagram_client.get(f"/api/v1/instagram/callback?code=auth-code&state={state}")

        second_state = start_oauth(instagram_client, auth_headers)
        response = instagram_client.get(
            f"/api/v1/instagram/callback?code=auth-code&state={second_state}"
        )
        assert response.status_code == 409


class TestConnectedEndpoints:
    @pytest.fixture
    def connected(self, instagram_client, auth_headers):
        state = start_oauth(instagram_client, auth_headers)
        instagram_client.get(f"/api/v1/instagram/callback?code=auth-code&state={state}")
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
