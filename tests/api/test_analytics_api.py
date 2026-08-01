import pytest

pytestmark = pytest.mark.api


class TestAccountAnalytics:
    def test_returns_analytics_for_the_connected_account(
        self, client, auth_headers, connected_account
    ):
        response = client.get("/api/v1/analytics/account", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert body["followers_count"] == 1200
        assert body["reach"] == 5000
        assert body["follower_growth"] == {"absolute": 200, "percentage": 20.0}

    def test_is_404_without_a_connected_account(self, client, auth_headers):
        assert client.get(
            "/api/v1/analytics/account", headers=auth_headers
        ).status_code == 404

    @pytest.mark.parametrize("days", [0, -1, 400])
    def test_rejects_an_out_of_range_window(self, client, auth_headers, days):
        response = client.get(f"/api/v1/analytics/account?days={days}", headers=auth_headers)
        assert response.status_code == 422


class TestMediaAnalytics:
    def test_returns_per_post_analytics(self, client, auth_headers, connected_account):
        response = client.get("/api/v1/analytics/media", headers=auth_headers)
        assert response.status_code == 200

        by_id = {item["media_id"]: item for item in response.json()}
        assert by_id["media_1"]["engagement_rate"] == 11.5
        assert by_id["media_2"]["engagement_rate"] == 9.25

    def test_filters_by_media_type(self, client, auth_headers, connected_account):
        response = client.get("/api/v1/analytics/media?media_type=REELS", headers=auth_headers)
        assert [item["media_id"] for item in response.json()] == ["media_2"]

    def test_respects_the_limit(self, client, auth_headers, connected_account):
        response = client.get("/api/v1/analytics/media?limit=1", headers=auth_headers)
        assert len(response.json()) == 1

    @pytest.mark.parametrize("limit", [0, 101])
    def test_rejects_an_out_of_range_limit(self, client, auth_headers, limit):
        response = client.get(f"/api/v1/analytics/media?limit={limit}", headers=auth_headers)
        assert response.status_code == 422


class TestTopContent:
    def test_ranks_by_engagement_rate_by_default(
        self, client, auth_headers, connected_account
    ):
        response = client.get("/api/v1/analytics/top-content", headers=auth_headers)
        assert response.json()["items"][0]["media_id"] == "media_1"

    def test_bottom_order_returns_the_weakest_first(
        self, client, auth_headers, connected_account
    ):
        response = client.get(
            "/api/v1/analytics/top-content?order=bottom", headers=auth_headers
        )
        assert response.json()["items"][0]["media_id"] == "media_2"

    def test_can_rank_by_another_metric(self, client, auth_headers, connected_account):
        response = client.get(
            "/api/v1/analytics/top-content?metric=likes&limit=1", headers=auth_headers
        )
        assert response.json()["items"][0]["media_id"] == "media_2"

    @pytest.mark.parametrize(
        "query",
        ["metric=nonsense", "order=sideways", "limit=0", "limit=51"],
    )
    def test_rejects_invalid_parameters(self, client, auth_headers, query):
        response = client.get(f"/api/v1/analytics/top-content?{query}", headers=auth_headers)
        assert response.status_code == 422


class TestTrends:
    def test_returns_bucketed_points(self, client, auth_headers, connected_account):
        response = client.get(
            "/api/v1/analytics/trends?granularity=daily&days=30", headers=auth_headers
        )
        assert response.status_code == 200

        body = response.json()
        assert body["granularity"] == "daily"
        assert sum(point["posts_count"] for point in body["points"]) == 2

    @pytest.mark.parametrize("granularity", ["daily", "weekly", "monthly"])
    def test_accepts_each_granularity(self, client, auth_headers, connected_account, granularity):
        response = client.get(
            f"/api/v1/analytics/trends?granularity={granularity}", headers=auth_headers
        )
        assert response.status_code == 200

    def test_rejects_an_unknown_granularity(self, client, auth_headers):
        response = client.get(
            "/api/v1/analytics/trends?granularity=yearly", headers=auth_headers
        )
        assert response.status_code == 422


class TestDashboard:
    def test_combines_all_three_sections(self, client, auth_headers, connected_account):
        response = client.get("/api/v1/analytics/dashboard", headers=auth_headers)
        assert response.status_code == 200

        body = response.json()
        assert body["account"]["followers_count"] == 1200
        assert body["top_content"]
        assert "recent_trend" in body

    def test_sections_agree_with_the_standalone_endpoints(
        self, client, auth_headers, connected_account
    ):
        """The dashboard shares one data fetch across its sections; that
        must not make its numbers drift from the dedicated endpoints."""
        dashboard = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
        account = client.get("/api/v1/analytics/account", headers=auth_headers).json()
        top = client.get("/api/v1/analytics/top-content?limit=5", headers=auth_headers).json()

        assert dashboard["account"] == account
        assert dashboard["top_content"] == top["items"]


class TestEmptyDataIsHandledGracefully:
    def test_connected_account_with_no_media_still_responds(self, client, db, auth_headers):
        """A freshly connected account has no media yet; the analytics
        endpoints must return empty results rather than fail."""
        from app.models.instagram_account import InstagramAccount

        db.add(InstagramAccount(
            user_id=1, instagram_user_id="ig-empty",
            username="empty", access_token="x",
        ))
        db.commit()

        assert client.get("/api/v1/analytics/media", headers=auth_headers).json() == []
        assert client.get(
            "/api/v1/analytics/top-content", headers=auth_headers
        ).json()["items"] == []

        account = client.get("/api/v1/analytics/account", headers=auth_headers).json()
        assert account["engagement_rate"] is None
        assert account["follower_growth"] is None

        assert client.get("/api/v1/analytics/dashboard", headers=auth_headers).status_code == 200
