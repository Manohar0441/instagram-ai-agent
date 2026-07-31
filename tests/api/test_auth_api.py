import pytest

pytestmark = pytest.mark.api

REGISTRATION = {
    "username": "newuser",
    "full_name": "New User",
    "email": "new@example.com",
    "password": "supersecret123",
}


class TestRegister:
    def test_creates_an_account(self, client):
        response = client.post("/api/v1/auth/register", json=REGISTRATION)
        assert response.status_code == 201
        assert response.json()["email"] == "new@example.com"

    def test_never_returns_the_password_or_its_hash(self, client):
        body = client.post("/api/v1/auth/register", json=REGISTRATION).json()
        assert "password" not in body
        assert "hashed_password" not in body

    def test_rejects_a_duplicate_username(self, client):
        client.post("/api/v1/auth/register", json=REGISTRATION)
        response = client.post(
            "/api/v1/auth/register", json={**REGISTRATION, "email": "other@example.com"}
        )
        assert response.status_code == 409

    def test_rejects_a_duplicate_email(self, client):
        client.post("/api/v1/auth/register", json=REGISTRATION)
        response = client.post(
            "/api/v1/auth/register", json={**REGISTRATION, "username": "different"}
        )
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "override, reason",
        [
            ({"email": "not-an-email"}, "malformed email"),
            ({"password": "short"}, "password below the minimum length"),
            ({"username": ""}, "empty username"),
        ],
    )
    def test_rejects_invalid_input(self, client, override, reason):
        response = client.post("/api/v1/auth/register", json={**REGISTRATION, **override})
        assert response.status_code == 422, reason


class TestLogin:
    def test_issues_a_bearer_token(self, client):
        client.post("/api/v1/auth/register", json=REGISTRATION)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "new@example.com", "password": "supersecret123"},
        )
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"
        assert response.json()["access_token"]

    def test_rejects_a_wrong_password(self, client):
        client.post("/api/v1/auth/register", json=REGISTRATION)
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "new@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_rejects_an_unknown_account(self, client):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody@example.com", "password": "supersecret123"},
        )
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
