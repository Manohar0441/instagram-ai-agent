"""Health checks, observability, and security headers."""
import pytest

pytestmark = pytest.mark.api


class TestHealthChecks:
    def test_liveness_never_depends_on_external_services(self, client):
        """Liveness answers 'should this process be restarted?', so it must
        stay green even when the database and cache table are unreachable."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_reports_dependency_status(self, client, fake_dynamodb):
        response = client.get("/health/ready")
        assert "database" in response.json()["checks"]
        assert "cache" in response.json()["checks"]

    def test_readiness_is_green_when_dependencies_answer(self, client, fake_dynamodb):
        """Both checks run for real here - the database check issues its
        SELECT against the test database and the cache check answers via
        the moto-mocked DynamoDB table."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        assert response.json()["checks"] == {"database": True, "cache": True}

    def test_readiness_turns_red_when_the_database_is_down(self, client, monkeypatch):
        import app.api.health as health_module

        monkeypatch.setattr(health_module, "_check_database", lambda: False)
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["database"] is False

    def test_readiness_turns_red_when_the_cache_is_down(self, client, monkeypatch):
        """A 503 here tells the load balancer to stop sending traffic to
        this instance without restarting it."""
        import app.api.health as health_module

        monkeypatch.setattr(health_module, "_check_cache", lambda: False)
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_health_summary_includes_app_metadata(self, client, fake_dynamodb):
        body = client.get("/health").json()
        assert body["app"]
        assert body["version"]
        assert body["environment"]
        assert body["uptime_seconds"] >= 0

    def test_health_endpoints_need_no_authentication(self, client):
        for path in ("/health", "/health/ready", "/health/live"):
            assert client.get(path).status_code in (200, 503)


class TestObservability:
    def test_every_response_carries_a_request_id(self, client):
        assert client.get("/").headers.get("X-Request-ID")

    def test_request_ids_are_unique_per_request(self, client):
        first = client.get("/").headers["X-Request-ID"]
        second = client.get("/").headers["X-Request-ID"]
        assert first != second

    def test_metrics_are_exposed_in_prometheus_format(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "# HELP" in response.text

    def test_metrics_track_request_counts(self, client):
        client.get("/health/live")
        assert "http_request" in client.get("/metrics").text


class TestSecurityHeaders:
    @pytest.mark.parametrize(
        "header, expected",
        [
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "strict-origin-when-cross-origin"),
        ],
    )
    def test_defensive_headers_are_present(self, client, header, expected):
        assert client.get("/").headers.get(header) == expected

    def test_hsts_is_set(self, client):
        assert "max-age=" in client.get("/").headers.get("Strict-Transport-Security", "")

    def test_headers_are_present_on_error_responses_too(self, client):
        response = client.get("/api/v1/auth/me")  # 401
        assert response.status_code == 401
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


class TestErrorResponsesDoNotLeakInternals:
    def test_unhandled_errors_return_a_generic_message(
        self, non_raising_client, auth_headers, monkeypatch
    ):
        """An unexpected failure must not put a stack trace, an exception
        type, or a connection string in the response body. The full detail
        is logged server-side instead."""
        import app.services.analytics_service as module

        def explode(self, user_id, days=30):
            raise RuntimeError("connection string postgres://user:password@host/db")

        monkeypatch.setattr(module.AnalyticsService, "get_account_analytics", explode)

        response = non_raising_client.get("/api/v1/analytics/account", headers=auth_headers)

        assert response.status_code == 500
        assert response.json() == {
            "detail": "An unexpected error occurred. Please try again later."
        }
        assert "password" not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text


class TestRateLimiting:
    def test_ai_endpoints_have_a_stricter_limit_than_the_default(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        """Insights costs an LLM call per miss, so it is limited well below
        the 100/minute applied to ordinary endpoints."""
        statuses = [
            client.get("/api/v1/insights", headers=auth_headers).status_code
            for _ in range(11)
        ]
        assert 429 in statuses
        assert statuses.index(429) <= 10
