from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal

from app.models.instagram_account import InstagramAccount
from app.models.instagram_media import InstagramMedia
from app.models.media_insight import MediaInsight
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.schemas.analytics import (
    AccountAnalyticsResponse,
    DashboardResponse,
    GrowthMetric,
    MediaAnalyticsResponse,
    TopContentResponse,
    TrendPoint,
    TrendsResponse,
)
from app.services.instagram_service import InstagramAccountNotConnectedError
from app.utils.analytics_calculations import (
    Granularity,
    RankOrder,
    as_aware_utc,
    average_or_none,
    bucket_start,
    calculate_engagement_rate,
    calculate_growth,
    rank_content,
    sum_or_none,
)

DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_DASHBOARD_TREND_DAYS = 7
DEFAULT_TOP_CONTENT_LIMIT = 5
ACCOUNT_INSIGHTS_PERIOD = "day"
PROFILE_SNAPSHOT_PERIOD = "profile"

# Maps a top-content "metric" query param to how it reads a computed
# MediaAnalyticsResponse. Add an entry here to expose a new ranking metric.
_METRIC_EXTRACTORS: dict[str, Callable[[MediaAnalyticsResponse], float | None]] = {
    "engagement_rate": lambda item: item.engagement_rate,
    "reach": lambda item: item.reach,
    "likes": lambda item: item.likes,
    "comments": lambda item: item.comments,
    "impressions": lambda item: item.impressions,
}


class AnalyticsService:
    """Derive account, content, and trend analytics from already-stored data.

    This service never calls the Graph API itself - it only reads what
    InstagramService has already fetched and persisted. Keeping ingestion
    and analysis separate avoids hitting Meta's rate limits on every
    dashboard load and keeps these endpoints fast.
    """

    def __init__(
        self,
        instagram_account_repository: InstagramAccountRepository,
        instagram_media_repository: InstagramMediaRepository,
        media_insight_repository: MediaInsightRepository,
        account_insight_repository: AccountInsightRepository,
    ) -> None:
        """Initialize the service with required repositories."""
        self.instagram_account_repository = instagram_account_repository
        self.instagram_media_repository = instagram_media_repository
        self.media_insight_repository = media_insight_repository
        self.account_insight_repository = account_insight_repository

    def get_account_analytics(
        self, user_id: int, days: int = DEFAULT_LOOKBACK_DAYS
    ) -> AccountAnalyticsResponse:
        """Return account-level analytics for the given lookback window."""
        account = self._get_connected_account(user_id)
        return self._account_analytics(account, days)

    def _account_analytics(
        self,
        account: InstagramAccount,
        days: int,
        media_analytics: list[MediaAnalyticsResponse] | None = None,
    ) -> AccountAnalyticsResponse:
        """Build account analytics, reusing already-computed media analytics if given."""
        since = datetime.now(timezone.utc) - timedelta(days=days)

        day_snapshots = self.account_insight_repository.list_by_account_id(
            account.id, period=ACCOUNT_INSIGHTS_PERIOD, since=since
        )
        latest_day = day_snapshots[-1] if day_snapshots else None
        metrics = latest_day.metrics if latest_day else {}

        follower_growth = self._compute_follower_growth(account.id, since)
        if media_analytics is None:
            media_analytics = self._compute_media_analytics(account.id)
        engagement_rate = average_or_none(
            [item.engagement_rate for item in media_analytics if item.engagement_rate is not None]
        )

        return AccountAnalyticsResponse(
            instagram_user_id=account.instagram_user_id,
            username=account.username,
            followers_count=account.followers_count,
            follower_growth=follower_growth,
            media_count=account.media_count,
            reach=metrics.get("reach"),
            impressions=metrics.get("impressions"),
            profile_visits=metrics.get("profile_views"),
            accounts_reached=metrics.get("reach"),
            accounts_engaged=metrics.get("accounts_engaged"),
            engagement_rate=engagement_rate,
            period_days=days,
            last_updated=latest_day.fetched_at if latest_day else None,
        )

    def get_media_analytics(
        self,
        user_id: int,
        limit: int = 25,
        media_type: str | None = None,
    ) -> list[MediaAnalyticsResponse]:
        """Return analytics for the user's posts and reels."""
        account = self._get_connected_account(user_id)
        return self._compute_media_analytics(account.id, media_type=media_type)[:limit]

    def get_top_content(
        self,
        user_id: int,
        limit: int = DEFAULT_TOP_CONTENT_LIMIT,
        metric: str = "engagement_rate",
        order: RankOrder = "top",
        days: int | None = None,
    ) -> TopContentResponse:
        """Return content ranked by a chosen metric, best or worst first.

        When days is given, only posts published within that window are
        ranked, so "best post last month" is answerable rather than being
        approximated by an all-time ranking.
        """
        account = self._get_connected_account(user_id)
        return self._top_content(account, limit, metric, order, days=days)

    def _top_content(
        self,
        account: InstagramAccount,
        limit: int,
        metric: str,
        order: RankOrder,
        media_analytics: list[MediaAnalyticsResponse] | None = None,
        days: int | None = None,
    ) -> TopContentResponse:
        """Rank content, reusing already-computed media analytics if given."""
        if media_analytics is None:
            media_analytics = self._compute_media_analytics(account.id)
        if days is not None:
            media_analytics = self._published_within(media_analytics, days)
        key_func = _METRIC_EXTRACTORS.get(metric, _METRIC_EXTRACTORS["engagement_rate"])
        ranked = rank_content(media_analytics, key_func, order, limit)
        return TopContentResponse(metric=metric, order=order, items=ranked)

    @staticmethod
    def _published_within(
        media_analytics: list[MediaAnalyticsResponse], days: int
    ) -> list[MediaAnalyticsResponse]:
        """Keep only posts published in the last N days.

        Posts with no recorded publish time are excluded rather than
        assumed recent - including them would silently misattribute
        undated content to whatever window the user asked about.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return [
            item
            for item in media_analytics
            if item.posted_at is not None and as_aware_utc(item.posted_at) >= since
        ]

    def get_trends(
        self,
        user_id: int,
        granularity: Granularity = "daily",
        days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> TrendsResponse:
        """Return historical performance bucketed by day, week, or month."""
        account = self._get_connected_account(user_id)
        return self._trends(account, granularity, days)

    def _trends(
        self,
        account: InstagramAccount,
        granularity: Granularity,
        days: int,
        media_analytics: list[MediaAnalyticsResponse] | None = None,
    ) -> TrendsResponse:
        """Build trend points, reusing already-computed media analytics if given."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        if media_analytics is None:
            media_analytics = self._compute_media_analytics(account.id)
        points = self._build_trend_points(account.id, since, granularity, media_analytics)
        return TrendsResponse(granularity=granularity, points=points)

    def get_dashboard(self, user_id: int) -> DashboardResponse:
        """Return a summarized dashboard combining account, content, and trend data.

        Resolves the account and computes media analytics exactly once, then
        shares both across all three sections. Calling the public
        get_account_analytics/get_top_content/get_trends here instead would
        re-run the same account lookup and media+insight fetch three times
        over.
        """
        account = self._get_connected_account(user_id)
        media_analytics = self._compute_media_analytics(account.id)

        account_analytics = self._account_analytics(
            account, DEFAULT_LOOKBACK_DAYS, media_analytics
        )
        top_content = self._top_content(
            account, DEFAULT_TOP_CONTENT_LIMIT, "engagement_rate", "top", media_analytics
        )
        trends = self._trends(
            account, "daily", DEFAULT_DASHBOARD_TREND_DAYS, media_analytics
        )
        return DashboardResponse(
            account=account_analytics,
            top_content=top_content.items,
            recent_trend=trends.points,
        )

    def _compute_follower_growth(
        self, instagram_account_id: int, since: datetime
    ) -> GrowthMetric | None:
        profile_snapshots = self.account_insight_repository.list_by_account_id(
            instagram_account_id, period=PROFILE_SNAPSHOT_PERIOD, since=since
        )
        if len(profile_snapshots) < 2:
            return None

        previous = profile_snapshots[0].metrics.get("followers_count")
        current = profile_snapshots[-1].metrics.get("followers_count")
        growth = calculate_growth(previous, current)
        if growth is None:
            return None
        return GrowthMetric(absolute=growth.absolute, percentage=growth.percentage)

    def _compute_media_analytics(
        self, instagram_account_id: int, media_type: str | None = None
    ) -> list[MediaAnalyticsResponse]:
        media_list = self.instagram_media_repository.list_by_account_id(instagram_account_id)
        if media_type:
            media_list = [media for media in media_list if media.media_type == media_type]
        if not media_list:
            return []

        insights_by_media_id = self.media_insight_repository.get_latest_by_media_ids(
            [media.id for media in media_list]
        )
        return [
            self._build_media_analytics(media, insights_by_media_id.get(media.id))
            for media in media_list
        ]

    def _build_media_analytics(
        self, media: InstagramMedia, insight: MediaInsight | None
    ) -> MediaAnalyticsResponse:
        metrics = insight.metrics if insight else {}
        reach = metrics.get("reach")
        engagements = self._total_engagements(media, insight)
        engagement_rate = calculate_engagement_rate(engagements, reach=reach)

        return MediaAnalyticsResponse(
            media_id=media.media_id,
            media_type=media.media_type,
            caption=media.caption,
            permalink=media.permalink,
            posted_at=media.posted_at,
            likes=media.like_count,
            comments=media.comments_count,
            shares=metrics.get("shares"),
            saves=metrics.get("saved"),
            reach=reach,
            impressions=metrics.get("impressions"),
            engagement_rate=engagement_rate,
            watch_time=metrics.get("ig_reels_avg_watch_time"),
            # Completion rate would require the video's total duration,
            # which isn't reliably available from the Graph API media
            # fields this app currently requests - left None rather than
            # guessing at an unverified field.
            completion_rate=None,
            insights_fetched_at=insight.fetched_at if insight else None,
        )

    def _build_trend_points(
        self,
        instagram_account_id: int,
        since: datetime,
        granularity: Granularity,
        media_analytics: list[MediaAnalyticsResponse],
    ) -> list[TrendPoint]:
        day_snapshots = self.account_insight_repository.list_by_account_id(
            instagram_account_id, period=ACCOUNT_INSIGHTS_PERIOD, since=since
        )
        profile_snapshots = self.account_insight_repository.list_by_account_id(
            instagram_account_id, period=PROFILE_SNAPSHOT_PERIOD, since=since
        )
        # Reuses the already-computed analytics rather than re-reading media
        # and insights from the database; engagement_rate on each item is
        # derived from exactly the same inputs this used to recompute.
        media_in_window = [
            item
            for item in media_analytics
            if item.posted_at is not None and as_aware_utc(item.posted_at) >= since
        ]

        buckets: dict = defaultdict(
            lambda: {
                "reach": [],
                "impressions": [],
                "profile_visits": [],
                "followers_count": None,
                "posts_count": 0,
                "engagement_rates": [],
            }
        )

        for snapshot in day_snapshots:
            bucket = buckets[bucket_start(snapshot.fetched_at, granularity)]
            if snapshot.metrics.get("reach") is not None:
                bucket["reach"].append(snapshot.metrics["reach"])
            if snapshot.metrics.get("impressions") is not None:
                bucket["impressions"].append(snapshot.metrics["impressions"])
            if snapshot.metrics.get("profile_views") is not None:
                bucket["profile_visits"].append(snapshot.metrics["profile_views"])

        # Iterated in chronological order (oldest first), so the last
        # snapshot written into a bucket is that bucket's end-of-period value.
        for snapshot in profile_snapshots:
            bucket = buckets[bucket_start(snapshot.fetched_at, granularity)]
            followers = snapshot.metrics.get("followers_count")
            if followers is not None:
                bucket["followers_count"] = followers

        for item in media_in_window:
            bucket = buckets[bucket_start(item.posted_at, granularity)]
            bucket["posts_count"] += 1
            if item.engagement_rate is not None:
                bucket["engagement_rates"].append(item.engagement_rate)

        return [
            TrendPoint(
                period_start=period_start,
                reach=sum_or_none(values["reach"]),
                impressions=sum_or_none(values["impressions"]),
                profile_visits=sum_or_none(values["profile_visits"]),
                followers_count=values["followers_count"],
                posts_count=values["posts_count"],
                average_engagement_rate=average_or_none(values["engagement_rates"]),
            )
            for period_start, values in sorted(buckets.items())
        ]

    @staticmethod
    def _total_engagements(media: InstagramMedia, insight: MediaInsight | None) -> int:
        likes = media.like_count or 0
        comments = media.comments_count or 0
        shares = (insight.metrics.get("shares") or 0) if insight else 0
        saves = (insight.metrics.get("saved") or 0) if insight else 0
        return likes + comments + shares + saves

    def _get_connected_account(self, user_id: int) -> InstagramAccount:
        account = self.instagram_account_repository.get_by_user_id(user_id)
        if account is None:
            raise InstagramAccountNotConnectedError("No Instagram account is connected for this user.")
        return account
