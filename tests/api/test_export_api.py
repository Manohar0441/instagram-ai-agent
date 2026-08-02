import pytest

pytestmark = pytest.mark.api


class TestBundleShape:
    def test_returns_a_full_bundle_with_all_sections_ok(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        response = client.get("/api/v1/export/full-report", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert body["meta"]["ai_sections_ok"] == 3
        assert body["meta"]["schema_version"] == 1
        assert body["insights"]["status"] == "ok"
        assert body["recommendations"]["status"] == "ok"
        assert body["report"]["status"] == "ok"
        assert body["analytics"]["account"]["followers_count"] == 1200
        assert len(body["analytics"]["inventory"]["items"]) == 2

        # `inputs` is populated for a healthy section too, not just a degraded one.
        assert body["insights"]["inputs"]["period_days"] == 30

    def test_404_without_a_connected_account(self, client, auth_headers, fake_structured_llm):
        response = client.get("/api/v1/export/full-report", headers=auth_headers)
        assert response.status_code == 404

    def test_default_window_is_30_days(self, client, auth_headers, connected_account, fake_structured_llm):
        response = client.get("/api/v1/export/full-report", headers=auth_headers)
        assert response.json()["meta"]["days"] == 30

    def test_invalid_window_is_rejected(self, client, auth_headers, connected_account, fake_structured_llm):
        response = client.get("/api/v1/export/full-report?days=45", headers=auth_headers)
        assert response.status_code == 422


class TestWindowGranularity:
    @pytest.mark.parametrize(
        "days,expected_granularity",
        [(7, "daily"), (14, "daily"), (30, "weekly"), (90, "weekly"), (180, "monthly"), (365, "monthly")],
    )
    def test_trend_granularity_follows_the_window(
        self, client, auth_headers, connected_account, fake_structured_llm, days, expected_granularity
    ):
        response = client.get(f"/api/v1/export/full-report?days={days}", headers=auth_headers)
        assert response.json()["analytics"]["trends"]["granularity"] == expected_granularity

    @pytest.mark.parametrize(
        "days,expected_period,covers_window",
        [(7, "weekly", True), (14, "monthly", False), (30, "monthly", True)],
    )
    def test_report_period_follows_the_window(
        self, client, auth_headers, connected_account, fake_structured_llm, days, expected_period, covers_window
    ):
        response = client.get(f"/api/v1/export/full-report?days={days}", headers=auth_headers)
        body = response.json()["report"]
        assert body["period_label"] == expected_period
        assert body["covers_export_window"] == covers_window


class TestDegradation:
    def test_not_configured_leaves_analytics_fully_populated(
        self, client, auth_headers, connected_account, fake_structured_llm, monkeypatch
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        response = client.get("/api/v1/export/full-report", headers=auth_headers)

        assert response.status_code == 200
        body = response.json()
        assert body["meta"]["ai_sections_ok"] == 0
        for section in ("insights", "recommendations", "report"):
            assert body[section]["status"] == "unavailable"
            assert body[section]["failure"]["reason"] == "not_configured"
            assert body[section]["failure"]["retriable"] is False
            assert body[section]["inputs"] is not None

        assert body["analytics"]["account"]["followers_count"] == 1200
        assert len(body["analytics"]["inventory"]["items"]) == 2

    def test_one_failing_section_does_not_affect_the_others(
        self, client, auth_headers, connected_account, monkeypatch
    ):
        import app.services.insights_service as insights_module

        class FailingLLM:
            def with_structured_output(self, schema):
                return self

            def invoke(self, messages):
                raise RuntimeError("insights provider is down")

        monkeypatch.setattr(insights_module, "build_llm", lambda api_key: FailingLLM())

        response = client.get("/api/v1/export/full-report", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["insights"]["status"] == "unavailable"
        assert body["insights"]["failure"]["reason"] == "unexpected_error"
        assert body["meta"]["ai_sections_ok"] == 0

    def test_unexpected_error_message_does_not_leak_internals(
        self, client, auth_headers, connected_account, monkeypatch
    ):
        import app.services.insights_service as insights_module
        import app.services.recommendation_service as recommendation_module
        import app.services.report_service as report_module

        class FailingLLM:
            def with_structured_output(self, schema):
                return self

            def invoke(self, messages):
                raise RuntimeError("connection string: postgres://user:hunter2@host")

        for module in (insights_module, recommendation_module, report_module):
            monkeypatch.setattr(module, "build_llm", lambda api_key: FailingLLM())

        response = client.get("/api/v1/export/full-report", headers=auth_headers)
        body = response.json()
        for section in ("insights", "recommendations", "report"):
            assert "hunter2" not in body[section]["failure"]["message"]
            assert "postgres://" not in body[section]["failure"]["message"]
