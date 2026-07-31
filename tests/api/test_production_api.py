"""Health checks, observability, security headers, and background jobs."""
import pytest

pytestmark = pytest.mark.api


class TestHealthChecks:
    def test_liveness_never_depends_on_external_services(self, client):
        """Liveness answers 'should this process be restarted?', so it must
        stay green even when the database and Redis are unreachable."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_reports_dependency_status(self, client, fake_redis):
        response = client.get("/health/ready")
        assert "database" in response.json()["checks"]
        assert "redis" in response.json()["checks"]

    def test_readiness_is_green_when_dependencies_answer(self, client, fake_redis):
        """Both checks run for real here - the database check issues its
        SELECT against the test database and Redis answers via the fake."""
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
        assert response.json()["checks"] == {"database": True, "redis": True}

    def test_readiness_turns_red_when_the_database_is_down(self, client, monkeypatch):
        import app.api.health as health_module

        monkeypatch.setattr(health_module, "_check_database", lambda: False)
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"]["database"] is False

    def test_readiness_turns_red_when_redis_is_down(self, client, monkeypatch):
        """A 503 here tells the load balancer to stop sending traffic to
        this instance without restarting it."""
        import app.api.health as health_module

        monkeypatch.setattr(health_module, "_check_redis", lambda: False)
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_health_summary_includes_app_metadata(self, client, fake_redis):
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


class TestBackgroundJobs:
    def test_enqueue_returns_202_with_a_job_id(
        self, client, auth_headers, connected_account, job_queue, worker_db, fake_structured_llm
    ):
        response = client.post("/api/v1/jobs/reports/weekly", headers=auth_headers)
        assert response.status_code == 202
        assert response.json()["job_id"]
        assert response.json()["status"] == "queued"

    def test_completed_job_exposes_the_report(
        self, client, auth_headers, connected_account, job_queue, worker_db, fake_structured_llm
    ):
        job_id = client.post(
            "/api/v1/jobs/reports/weekly", headers=auth_headers
        ).json()["job_id"]

        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "finished"
        assert response.json()["result"]["period"] == "weekly"

    def test_another_user_cannot_read_the_job(
        self, client, auth_headers, connected_account, other_auth_headers,
        job_queue, worker_db, fake_structured_llm,
    ):
        job_id = client.post(
            "/api/v1/jobs/reports/weekly", headers=auth_headers
        ).json()["job_id"]

        response = client.get(f"/api/v1/jobs/{job_id}", headers=other_auth_headers)
        assert response.status_code == 404

    def test_unknown_job_id_is_404(self, client, auth_headers, job_queue):
        assert client.get(
            "/api/v1/jobs/does-not-exist", headers=auth_headers
        ).status_code == 404

    def test_rejects_an_unsupported_period(self, client, auth_headers, job_queue):
        assert client.post(
            "/api/v1/jobs/reports/daily", headers=auth_headers
        ).status_code == 422


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
