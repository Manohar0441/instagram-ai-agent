import pytest

from tests.conftest import USER_PASSWORD

pytestmark = pytest.mark.api


class TestRegistrationIsDisabled:
    """Regression test: this app has exactly one user, created directly in
    the database (scripts/create_user.py) - self-service registration must
    stay unreachable, not just unlinked from the login page."""

    def test_there_is_no_register_endpoint(self, client):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "intruder",
                "full_name": "Intruder",
                "email": "intruder@example.com",
                "password": "supersecret123",
            },
        )
        assert response.status_code in (404, 405)


class TestLogin:
    def test_issues_a_bearer_token(self, client, db_user):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "creator1@example.com", "password": USER_PASSWORD},
        )
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["access_token"]
        assert response.json()["refresh_token"]

    def test_rejects_a_wrong_password(self, client, db_user):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "creator1@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_rejects_an_unknown_account(self, client):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "supersecret123"},
        )
        assert response.status_code == 401


class TestRefresh:
    def test_issues_a_new_token_pair(self, client, db_user):
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "creator1@example.com", "password": USER_PASSWORD},
        )
        refresh_token = login.json()["refresh_token"]

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        assert response.json()["access_token"]
        assert response.json()["refresh_token"]

        # The new access token actually works.
        me = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["email"] == "creator1@example.com"

    def test_rejects_an_access_token(self, client, db_user):
        """An access token must never work as a refresh token."""
        login = client.post(
            "/api/v1/auth/login",
            data={"username": "creator1@example.com", "password": USER_PASSWORD},
        )
        access_token = login.json()["access_token"]

        response = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert response.status_code == 401

    def test_rejects_garbage(self, client):
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )
        assert response.status_code == 401

    def test_rejects_an_expired_refresh_token(self, client, db_user):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from app.core.settings import settings

        expired = pyjwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                "type": "refresh",
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = client.post("/api/v1/auth/refresh", json={"refresh_token": expired})
        assert response.status_code == 401


class TestCurrentUser:
    def test_returns_the_authenticated_user(self, client, auth_headers):
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "creator1@example.com"

    def test_requires_a_token(self, client):
        assert client.get("/api/v1/auth/me").status_code == 401

    @pytest.mark.parametrize(
        "header",
        [
            {"Authorization": "Bearer not-a-real-token"},
            {"Authorization": "Bearer "},
            {"Authorization": "creator1@example.com"},
        ],
    )
    def test_rejects_malformed_credentials(self, client, header):
        assert client.get("/api/v1/auth/me", headers=header).status_code == 401

    def test_rejects_an_oauth_state_token(self, client, auth_headers):
        """Regression test: OAuth state tokens are signed with the same key
        and are exposed in URLs, so they must not authenticate API calls."""
        from app.utils.jwt import create_oauth_state_token

        state_token = create_oauth_state_token(1)
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {state_token}"}
        )
        assert response.status_code == 401

    def test_non_numeric_subject_is_rejected_not_a_server_error(self, client):
        """Regression test: this used to raise ValueError past the handler
        and surface as a 500."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from app.core.settings import settings

        token = pyjwt.encode(
            {
                "sub": "not-a-number",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "type": "access",
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


class TestRateLimiting:
    def test_repeated_login_attempts_are_throttled(self, client):
        """Brute-forcing a password must hit a limit well before it becomes
        practical."""
        statuses = [
            client.post(
                "/api/v1/auth/login",
                data={"username": "nobody@example.com", "password": "guess"},
            ).status_code
            for _ in range(6)
        ]
        assert statuses[:5] == [401] * 5
        assert statuses[5] == 429
