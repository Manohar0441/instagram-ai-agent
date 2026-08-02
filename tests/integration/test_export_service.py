from datetime import timedelta

import pytest

from app.models.instagram_media import InstagramMedia
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_credential_service import AICredentialService
from app.services.analytics_service import AnalyticsService
from app.services.export_service import FullReportExportService
from app.services.insights_service import InsightsService
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
def export_service(analytics_service, credential_service):
    return FullReportExportService(
        analytics_service,
        InsightsService(analytics_service, credential_service),
        RecommendationService(analytics_service, credential_service),
        ReportService(analytics_service, credential_service),
    )


class TestExportAntiDrift:
    """The whole point of `inputs` is that it's what the AI actually saw -
    prove it matches ai_context's own output, not a second derivation."""

    def test_insights_inputs_match_what_the_ai_context_builder_produces(
        self, export_service, analytics_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        from app.services.ai_context import build_insights_context

        bundle = export_service.generate_export(db_user.id, days=30)
        expected = build_insights_context(analytics_service, db_user.id, 30)

        assert bundle.insights.inputs == expected.inputs

    def test_recommendations_inputs_match_what_the_ai_context_builder_produces(
        self, export_service, analytics_service, fake_structured_llm, db_user, connected_account_for_db_user
    ):
        from app.services.ai_context import build_recommendations_context

        bundle = export_service.generate_export(db_user.id, days=30)
        expected = build_recommendations_context(analytics_service, db_user.id, 30)

        assert bundle.recommendations.inputs == expected.inputs


class TestExportAnalytics:
    def test_undated_posts_are_excluded_and_counted(
        self, export_service, db, db_user, connected_account_for_db_user, fake_structured_llm
    ):
        db.add(InstagramMedia(
            instagram_account_id=connected_account_for_db_user.id,
            media_id="media_undated",
            media_type="IMAGE",
            caption="No timestamp",
            permalink="https://instagram.com/p/undated",
            posted_at=None,
            like_count=1,
            comments_count=0,
        ))
        db.commit()

        bundle = export_service.generate_export(db_user.id, days=30)

        inventory_ids = {item.media_id for item in bundle.analytics.inventory.items}
        assert "media_undated" not in inventory_ids
        assert bundle.analytics.inventory.excluded_undated_count == 1

    def test_inventory_truncation_is_disclosed(
        self, export_service, db, db_user, connected_account_for_db_user, fake_structured_llm, monkeypatch
    ):
        import app.services.export_service as export_module

        monkeypatch.setattr(export_module, "INVENTORY_LIMIT", 1)

        bundle = export_service.generate_export(db_user.id, days=30)

        assert bundle.analytics.inventory.limit == 1
        assert bundle.analytics.inventory.total_in_window == 2
        assert len(bundle.analytics.inventory.items) == 1
        assert bundle.analytics.inventory.truncated is True


class TestKeystoneDegradation:
    """Analytics must survive a total AI outage - that's the entire reason
    `inputs` is gathered independently of the AI service calls."""

    def test_analytics_and_inputs_stay_fully_populated_during_a_total_ai_outage(
        self, export_service, db_user, connected_account_for_db_user, monkeypatch
    ):
        import app.services.insights_service as insights_module
        import app.services.recommendation_service as recommendation_module
        import app.services.report_service as report_module

        class ExplodingLLM:
            def with_structured_output(self, schema):
                return self

            def invoke(self, messages):
                raise RuntimeError("upstream is completely down")

        for module in (insights_module, recommendation_module, report_module):
            monkeypatch.setattr(module, "build_llm", lambda api_key: ExplodingLLM())

        bundle = export_service.generate_export(db_user.id, days=30)

        assert bundle.insights.status == "unavailable"
        assert bundle.recommendations.status == "unavailable"
        assert bundle.report.status == "unavailable"
        assert bundle.meta.ai_sections_ok == 0

        assert bundle.analytics.account.followers_count == 1200
        assert len(bundle.analytics.inventory.items) == 2
        assert bundle.insights.inputs.account_analytics.followers_count == 1200
        assert bundle.recommendations.inputs.sample.returned == 2
        assert bundle.report.inputs.account_analytics.followers_count == 1200
