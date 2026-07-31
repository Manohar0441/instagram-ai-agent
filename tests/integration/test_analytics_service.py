import pytest
from sqlalchemy import event

from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.services.analytics_service import AnalyticsService
from app.services.instagram_service import InstagramAccountNotConnectedError

pytestmark = pytest.mark.integration


@pytest.fixture
def analytics_service(db):
    return AnalyticsService(
        InstagramAccountRepository(db),
        InstagramMediaRepository(db),
        MediaInsightRepository(db),
        AccountInsightRepository(db),
    )


class TestAccountAnalytics:
    def test_raises_when_no_account_is_connected(self, analytics_service, db_user):
        with pytest.raises(InstagramAccountNotConnectedError):
            analytics_service.get_account_analytics(db_user.id)

    def test_reports_the_latest_daily_snapshot(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        """Two daily snapshots are seeded; the newer (reach 5000) wins over
        the older (reach 3000)."""
        result = analytics_service.get_account_analytics(db_user.id)
        assert result.reach == 5000
        assert result.impressions == 6000
        assert result.profile_visits == 200

    def test_computes_follower_growth_from_history(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        result = analytics_service.get_account_analytics(db_user.id)
        assert result.follower_growth.absolute == 200
        assert result.follower_growth.percentage == 20.0

    def test_follower_growth_is_none_without_two_snapshots(
        self, analytics_service, db, db_user, connected_account_for_db_user
    ):
        from app.models.account_insight import AccountInsight

        db.query(AccountInsight).filter(AccountInsight.period == "profile").delete()
        db.commit()
        assert analytics_service.get_account_analytics(db_user.id).follower_growth is None


class TestMediaAnalytics:
    def test_uses_only_the_most_recent_insight_per_media(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        """media_1 has two snapshots (reach 800 then 1000); the stale one
        must not be used."""
        by_id = {m.media_id: m for m in analytics_service.get_media_analytics(db_user.id)}
        assert by_id["media_1"].reach == 1000

    def test_computes_reach_normalized_engagement_rates(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        by_id = {m.media_id: m for m in analytics_service.get_media_analytics(db_user.id)}
        assert by_id["media_1"].engagement_rate == 11.5
        assert by_id["media_2"].engagement_rate == 9.25

    def test_surfaces_watch_time_when_present(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        by_id = {m.media_id: m for m in analytics_service.get_media_analytics(db_user.id)}
        assert by_id["media_2"].watch_time == 4500
        assert by_id["media_1"].watch_time is None

    def test_filters_by_media_type(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        results = analytics_service.get_media_analytics(db_user.id, media_type="REELS")
        assert [m.media_id for m in results] == ["media_2"]

    def test_respects_the_limit(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        assert len(analytics_service.get_media_analytics(db_user.id, limit=1)) == 1

    def test_returns_empty_when_no_media_exists(self, analytics_service, db, db_user):
        from app.models.instagram_account import InstagramAccount

        db.add(InstagramAccount(
            user_id=db_user.id, instagram_user_id="ig-empty", facebook_page_id="p",
            username="empty", access_token="x",
        ))
        db.commit()
        assert analytics_service.get_media_analytics(db_user.id) == []


class TestTopContent:
    def test_ranks_by_engagement_rate_not_raw_likes(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        """media_2 has 5x the likes but a lower rate, because its reach is
        8x larger. The rate-based ranking must put media_1 first."""
        result = analytics_service.get_top_content(db_user.id, limit=2)
        assert [i.media_id for i in result.items] == ["media_1", "media_2"]

    def test_bottom_order_reverses_the_ranking(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        result = analytics_service.get_top_content(db_user.id, limit=2, order="bottom")
        assert [i.media_id for i in result.items] == ["media_2", "media_1"]

    def test_can_rank_by_raw_likes_instead(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        result = analytics_service.get_top_content(db_user.id, limit=1, metric="likes")
        assert result.items[0].media_id == "media_2"

    def test_unknown_metric_falls_back_to_engagement_rate(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        result = analytics_service.get_top_content(db_user.id, limit=1, metric="nonsense")
        assert result.items[0].media_id == "media_1"


class TestTrends:
    def test_counts_every_seeded_post_across_buckets(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        trends = analytics_service.get_trends(db_user.id, granularity="daily", days=30)
        assert sum(p.posts_count for p in trends.points) == 2

    def test_buckets_are_chronological(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        points = analytics_service.get_trends(db_user.id, days=30).points
        assert [p.period_start for p in points] == sorted(p.period_start for p in points)

    def test_narrow_window_excludes_older_posts(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        """media_1 is 3 days old, media_2 is 1 day old; a 2-day window
        should only see media_2."""
        trends = analytics_service.get_trends(db_user.id, granularity="daily", days=2)
        assert sum(p.posts_count for p in trends.points) == 1


class TestDashboard:
    def test_sections_match_the_standalone_endpoints(
        self, analytics_service, db_user, connected_account_for_db_user
    ):
        """The dashboard shares one account lookup and one media-analytics
        computation across its three sections; that optimization must not
        change any of the values it produces."""
        dashboard = analytics_service.get_dashboard(db_user.id)
        assert dashboard.account == analytics_service.get_account_analytics(db_user.id)
        assert dashboard.top_content == analytics_service.get_top_content(db_user.id, limit=5).items
        assert dashboard.recent_trend == analytics_service.get_trends(
            db_user.id, granularity="daily", days=7
        ).points

    def test_does_not_refetch_the_same_data_per_section(
        self, analytics_service, db, db_user, connected_account_for_db_user
    ):
        """Regression guard for the Milestone 9 fix: the dashboard used to
        re-run the account lookup and the media+insight fetch once per
        section, costing 13 queries."""
        queries = []

        @event.listens_for(db.get_bind(), "before_cursor_execute")
        def record(conn, cursor, statement, params, context, executemany):
            if statement.strip().upper().startswith("SELECT"):
                queries.append(statement)

        try:
            db.expire_all()
            analytics_service.get_dashboard(db_user.id)
        finally:
            event.remove(db.get_bind(), "before_cursor_execute", record)

        assert len(queries) <= 8, f"dashboard issued {len(queries)} SELECTs"

    def test_raises_when_no_account_is_connected(self, analytics_service, db_user):
        with pytest.raises(InstagramAccountNotConnectedError):
            analytics_service.get_dashboard(db_user.id)


class TestUserIsolation:
    def test_one_users_analytics_are_invisible_to_another(
        self, analytics_service, db, db_user, connected_account_for_db_user
    ):
        from app.models.user import User

        other = User(
            username="intruder", full_name="Intruder",
            email="intruder@example.com", hashed_password="x",
        )
        db.add(other)
        db.commit()

        with pytest.raises(InstagramAccountNotConnectedError):
            analytics_service.get_media_analytics(other.id)
