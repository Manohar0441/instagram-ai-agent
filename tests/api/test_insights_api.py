import pytest
from langchain_google_genai._common import GoogleGenerativeAIError

pytestmark = pytest.mark.api

AI_ENDPOINTS = [
    "/api/v1/insights",
    "/api/v1/recommendations",
    "/api/v1/reports/weekly",
    "/api/v1/reports/monthly",
]


class TestInsights:
    def test_returns_narratives_backed_by_real_figures(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        """The stub model returns prose containing no numbers, so every
        figure below must have come from the analytics layer."""
        response = client.get("/api/v1/insights", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert body["account_performance"]["summary"] == "Account narrative."
        assert body["account_performance"]["supporting_data"]["followers_count"] == 1200
        assert body["growth_trend"]["supporting_data"]["follower_growth"]["absolute"] == 200

    def test_covers_all_five_insight_categories(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        body = client.get("/api/v1/insights", headers=auth_headers).json()
        for category in (
            "account_performance", "content_performance", "growth_trend",
            "engagement_trend", "audience_behavior",
        ):
            assert body[category]["summary"], f"{category} has no narrative"


class TestRecommendations:
    def test_returns_actionable_fields(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        response = client.get("/api/v1/recommendations", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert body["content_ideas"] == ["Idea one", "Idea two"]
        assert body["engagement_reach_tips"]


class TestReports:
    @pytest.mark.parametrize("period", ["weekly", "monthly"])
    def test_returns_a_report_for_each_period(
        self, client, auth_headers, connected_account, fake_structured_llm, period
    ):
        response = client.get(f"/api/v1/reports/{period}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["period"] == period

    def test_content_rankings_come_from_stored_analytics(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        body = client.get("/api/v1/reports/weekly", headers=auth_headers).json()
        assert body["top_performing_content"][0]["media_id"] == "media_1"
        assert body["underperforming_content"][0]["media_id"] == "media_2"

    def test_includes_the_generated_narrative_sections(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        body = client.get("/api/v1/reports/weekly", headers=auth_headers).json()
        assert body["summary"] == "A solid period."
        assert body["key_strengths"] == ["Strength one"]
        assert body["actionable_next_steps"] == ["Step one"]


class TestCaching:
    def test_a_repeat_request_is_served_from_cache(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        """Each of these endpoints costs one LLM call, so a repeat within the
        TTL must not regenerate."""
        client.get("/api/v1/insights", headers=auth_headers)
        client.get("/api/v1/insights", headers=auth_headers)
        assert fake_structured_llm.call_count == 1

    def test_cached_responses_are_identical(
        self, client, auth_headers, connected_account, fake_structured_llm
    ):
        first = client.get("/api/v1/insights", headers=auth_headers).json()
        second = client.get("/api/v1/insights", headers=auth_headers).json()
        assert first == second

    def test_a_redis_outage_still_serves_the_request(
        self, client, auth_headers, connected_account, fake_structured_llm, monkeypatch
    ):
        """Caching is an optimization; losing Redis must degrade to
        regenerating, never to failing."""
        import redis

        from app.utils import cache

        class BrokenRedis:
            def get(self, key):
                raise redis.ConnectionError("down")

            def setex(self, key, ttl, value):
                raise redis.ConnectionError("down")

        monkeypatch.setattr(cache, "get_redis_client", lambda: BrokenRedis())

        assert client.get("/api/v1/insights", headers=auth_headers).status_code == 200
        assert client.get("/api/v1/insights", headers=auth_headers).status_code == 200
        assert fake_structured_llm.call_count == 2  # regenerated both times


class TestErrorHandling:
    @pytest.mark.parametrize("path", AI_ENDPOINTS)
    def test_404_without_a_connected_account(
        self, client, auth_headers, fake_structured_llm, path
    ):
        assert client.get(path, headers=auth_headers).status_code == 404

    @pytest.mark.parametrize("path", AI_ENDPOINTS)
    def test_503_when_the_ai_is_not_configured(
        self, client, auth_headers, connected_account, fake_structured_llm, path, monkeypatch
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        assert client.get(path, headers=auth_headers).status_code == 503

    @pytest.mark.parametrize("path", AI_ENDPOINTS)
    def test_502_when_the_provider_fails(
        self, client, auth_headers, connected_account, path, monkeypatch
    ):
        import app.services.insights_service as insights_module
        import app.services.recommendation_service as recommendation_module
        import app.services.report_service as report_module

        class FailingLLM:
            def with_structured_output(self, schema):
                return self

            def invoke(self, messages):
                raise GoogleGenerativeAIError("upstream down")

        for module in (insights_module, recommendation_module, report_module):
            monkeypatch.setattr(module, "build_llm", lambda: FailingLLM())

        assert client.get(path, headers=auth_headers).status_code == 502
