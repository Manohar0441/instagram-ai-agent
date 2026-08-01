import pytest
from langchain_google_genai._common import GoogleGenerativeAIError

from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_credential_service import AICredentialService
from app.services.ai_generation import AINotConfiguredError, AIProviderError
from app.services.ai_service import AIService
from app.services.ai_tools import build_tools
from app.services.analytics_service import AnalyticsService
from app.services.insights_service import InsightsService
from app.services.instagram_service import InstagramAccountNotConnectedError
from app.services.recommendation_service import RecommendationService
from app.services.report_service import ReportService

pytestmark = pytest.mark.integration


@pytest.fixture
def analytics_service(db):
    return AnalyticsService(
        InstagramAccountRepository(db),
        InstagramMediaRepository(db),
        MediaInsightRepository(db),
        AccountInsightRepository(db),
    )


@pytest.fixture
def credential_service(db):
    return AICredentialService(UserRepository(db))


@pytest.fixture
def insights_service(analytics_service, credential_service):
    return InsightsService(analytics_service, credential_service)


@pytest.fixture
def recommendation_service(analytics_service, credential_service):
    return RecommendationService(analytics_service, credential_service)


@pytest.fixture
def report_service(analytics_service, credential_service):
    return ReportService(analytics_service, credential_service)


class TestInsightsGrounding:
    def test_supporting_data_comes_from_the_database_not_the_model(
        self, insights_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        """The fake model returns fixed prose that mentions no numbers. Every
        figure in the response must therefore have come from the analytics
        layer, which is the whole grounding guarantee."""
        result = insights_service.get_insights(db_user.id)

        assert result.account_performance.summary == "Account narrative."
        assert result.account_performance.supporting_data["followers_count"] == 1200
        assert result.growth_trend.supporting_data["follower_growth"]["absolute"] == 200
        assert result.content_performance.supporting_data["post_count"] == 2

    def test_requires_a_connected_account(self, insights_service, fake_structured_llm, db_user):
        with pytest.raises(InstagramAccountNotConnectedError):
            insights_service.get_insights(db_user.id)

    def test_requires_configuration(
        self, insights_service, fake_structured_llm, db_user,
        connected_account_for_db_user, monkeypatch,
    ):
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        with pytest.raises(AINotConfiguredError):
            insights_service.get_insights(db_user.id)

    def test_upstream_failure_becomes_a_provider_error(
        self, insights_service, db_user, connected_account_for_db_user, monkeypatch
    ):
        import app.services.insights_service as module

        class FailingLLM:
            def with_structured_output(self, schema):
                return self

            def invoke(self, messages):
                raise GoogleGenerativeAIError("upstream down")

        monkeypatch.setattr(module, "build_llm", lambda api_key: FailingLLM())
        with pytest.raises(AIProviderError):
            insights_service.get_insights(db_user.id)


class TestInsightsCaching:
    def test_second_call_within_the_ttl_skips_generation(
        self, insights_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        insights_service.get_insights(db_user.id)
        insights_service.get_insights(db_user.id)
        assert fake_structured_llm.call_count == 1

    def test_different_users_do_not_share_a_cache_entry(
        self, insights_service, fake_structured_llm, db, db_user,
        connected_account_for_db_user,
    ):
        """A shared cache key would serve one user another's analytics."""
        from tests.conftest import seed_connected_account
        from app.models.user import User

        other = User(
            username="other", full_name="Other",
            email="other@example.com", hashed_password="x",
        )
        db.add(other)
        db.commit()
        seed_connected_account(
            db, user_id=other.id,
            instagram_user_id="17841499999999999", media_id_prefix="other",
        )

        first = insights_service.get_insights(db_user.id)
        second = insights_service.get_insights(other.id)

        assert fake_structured_llm.call_count == 2
        assert first.account_performance.supporting_data["instagram_user_id"] != (
            second.account_performance.supporting_data["instagram_user_id"]
        )


class TestRecommendations:
    def test_returns_the_generated_narratives(
        self, recommendation_service, fake_structured_llm, db_user,
        connected_account_for_db_user,
    ):
        result = recommendation_service.get_recommendations(db_user.id)
        assert result.content_ideas == ["Idea one", "Idea two"]
        assert result.best_posting_times == "Post in the evening."

    def test_requires_a_connected_account(
        self, recommendation_service, fake_structured_llm, db_user
    ):
        with pytest.raises(InstagramAccountNotConnectedError):
            recommendation_service.get_recommendations(db_user.id)


class TestReports:
    def test_content_lists_come_from_analytics_not_the_model(
        self, report_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        report = report_service.generate_report(db_user.id, period="weekly")

        assert report.summary == "A solid period."
        assert report.top_performing_content[0].media_id == "media_1"
        assert report.underperforming_content[0].media_id == "media_2"

    def test_weekly_and_monthly_use_different_windows(
        self, report_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        weekly = report_service.generate_report(db_user.id, period="weekly")
        monthly = report_service.generate_report(db_user.id, period="monthly")

        assert weekly.period == "weekly"
        assert monthly.period == "monthly"
        assert monthly.period_start < weekly.period_start

    def test_weekly_and_monthly_are_cached_separately(
        self, report_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        report_service.generate_report(db_user.id, period="weekly")
        report_service.generate_report(db_user.id, period="monthly")
        report_service.generate_report(db_user.id, period="weekly")
        assert fake_structured_llm.call_count == 2


class TestAgentTools:
    def test_tools_do_not_expose_a_user_id_parameter(self, analytics_service):
        """user_id is bound by closure precisely so the model cannot choose
        whose analytics to read. If it ever appears in a tool's schema, a
        prompt-injected value could reach the service layer."""
        tools = build_tools(analytics_service, user_id=1)

        assert tools, "expected the agent to have tools"
        for tool in tools:
            properties = tool.args_schema.model_json_schema().get("properties", {})
            assert "user_id" not in properties, f"{tool.name} exposes user_id"

    def test_tools_report_a_missing_connection_as_data(self, analytics_service, db_user):
        """The agent should explain the situation conversationally, so the
        tool returns a message rather than raising."""
        tools = {t.name: t for t in build_tools(analytics_service, user_id=db_user.id)}
        result = tools["get_account_performance"].invoke({"days": 7})
        assert "No Instagram account is connected" in result

    def test_tools_return_real_analytics(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        tools = {t.name: t for t in build_tools(analytics_service, user_id=db_user.id)}
        result = tools["get_account_performance"].invoke({"days": 30})
        assert '"followers_count":1200' in result.replace(" ", "")

    def test_tool_ignores_an_injected_user_id_argument(
        self, analytics_service, db, db_user, connected_account_for_db_user
    ):
        """Extra arguments the model invents are dropped by the schema
        binding; the closure-bound user is what actually gets queried."""
        from app.models.user import User

        intruder = User(
            username="intruder", full_name="Intruder",
            email="intruder@example.com", hashed_password="x",
        )
        db.add(intruder)
        db.commit()

        tools = {t.name: t for t in build_tools(analytics_service, user_id=intruder.id)}
        result = tools["get_account_performance"].invoke(
            {"days": 7, "user_id": db_user.id}
        )
        assert "No Instagram account is connected" in result


class TestAIServiceHealth:
    def test_reports_unavailable_without_a_key(
        self, analytics_service, credential_service, db_user, monkeypatch
    ):
        """No stored key and no server fallback leaves the user unconfigured."""
        from app.core.settings import settings

        monkeypatch.setattr(settings, "GOOGLE_API_KEY", None)
        health = AIService(analytics_service, credential_service).health_check(db_user.id)
        assert health.status == "unavailable"
        assert health.configured is False

    def test_reports_ok_with_a_key(self, analytics_service, credential_service, db_user):
        health = AIService(analytics_service, credential_service).health_check(db_user.id)
        assert health.status == "ok"
        assert health.configured is True
