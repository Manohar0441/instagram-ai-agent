"""Authorization coverage: what an unauthenticated caller can reach, and
what one authenticated user can learn about another.
"""
import pytest

pytestmark = pytest.mark.api

# Every endpoint that must reject an anonymous caller.
PROTECTED_ENDPOINTS = [
    ("GET", "/api/v1/auth/me"),
    ("GET", "/api/v1/users/1"),
    ("GET", "/api/v1/analytics/account"),
    ("GET", "/api/v1/analytics/media"),
    ("GET", "/api/v1/analytics/trends"),
    ("GET", "/api/v1/analytics/top-content"),
    ("GET", "/api/v1/analytics/dashboard"),
    ("GET", "/api/v1/instagram/connect"),
    ("GET", "/api/v1/instagram/profile"),
    ("GET", "/api/v1/instagram/media"),
    ("GET", "/api/v1/instagram/insights"),
    ("DELETE", "/api/v1/instagram/disconnect"),
    ("POST", "/api/v1/ai/chat"),
    ("GET", "/api/v1/ai/health"),
    ("GET", "/api/v1/insights"),
    ("GET", "/api/v1/recommendations"),
    ("GET", "/api/v1/reports/weekly"),
    ("GET", "/api/v1/reports/monthly"),
    ("POST", "/api/v1/jobs/reports/weekly"),
    ("GET", "/api/v1/jobs/some-job-id"),
]

PUBLIC_ENDPOINTS = [
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("GET", "/metrics"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    # The OAuth callback cannot carry an Authorization header - a browser
    # redirect from Meta has none. It authenticates via its signed state
    # parameter instead.
    ("GET", "/api/v1/instagram/callback"),
]


@pytest.mark.parametrize("method, path", PROTECTED_ENDPOINTS)
def test_protected_endpoints_reject_anonymous_callers(client, method, path):
    response = client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code == 401, f"{method} {path} did not require authentication"


@pytest.mark.parametrize("method, path", PUBLIC_ENDPOINTS)
def test_public_endpoints_are_reachable_without_a_token(client, method, path):
    """These are public by design; the test exists so that making one of
    them public accidentally is a deliberate, visible change."""
    response = client.request(method, path, json={} if method == "POST" else None)
    assert response.status_code != 401, f"{method} {path} unexpectedly requires authentication"


class TestNoCrossUserAccess:
    def test_a_user_cannot_read_another_users_record(
        self, client, auth_headers, other_auth_headers
    ):
        """Returns 404 rather than 403 on purpose: a 403 would confirm the
        ID exists, which is a user-enumeration oracle."""
        response = client.get("/api/v1/users/1", headers=other_auth_headers)
        assert response.status_code == 404

    def test_a_user_can_read_their_own_record(self, client, auth_headers):
        response = client.get("/api/v1/users/1", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "creator1@example.com"

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/analytics/account",
            "/api/v1/analytics/media",
            "/api/v1/analytics/dashboard",
            "/api/v1/instagram/profile",
        ],
    )
    def test_another_users_instagram_data_is_not_reachable(
        self, client, connected_account, other_auth_headers, path
    ):
        """User 1 has a connected account with data; user 2 must see none
        of it, and must be told only that they have no connection."""
        response = client.get(path, headers=other_auth_headers)
        assert response.status_code == 404


class TestUserEnumerationIsNotPossible:
    def test_there_is_no_endpoint_that_lists_all_users(self, client, auth_headers):
        """Regression test: GET /users used to return every account,
        including email addresses, with no authentication at all."""
        response = client.get("/api/v1/users", headers=auth_headers)
        assert response.status_code in (404, 405)

    def test_users_cannot_be_created_outside_registration(self, client):
        """Regression test: POST /users duplicated registration while
        bypassing its brute-force rate limit."""
        response = client.post(
            "/api/v1/users",
            json={
                "username": "sneaky",
                "full_name": "Sneaky",
                "email": "sneaky@example.com",
                "password": "supersecret123",
            },
        )
        assert response.status_code in (404, 405)
