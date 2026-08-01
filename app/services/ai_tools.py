from langchain_core.tools import BaseTool, tool

from app.services.analytics_service import AnalyticsService
from app.services.instagram_service import InstagramAccountNotConnectedError

NOT_CONNECTED_MESSAGE = (
    "No Instagram account is connected for this user. Tell them they need to "
    "connect an Instagram Business/Creator account before analytics are available."
)

_VALID_GRANULARITIES = ("daily", "weekly", "monthly")
_VALID_METRICS = ("engagement_rate", "reach", "likes", "comments", "impressions")
_VALID_ORDERS = ("top", "bottom")


def build_tools(analytics_service: AnalyticsService, user_id: int) -> list[BaseTool]:
    """Build the agent's analytics tools, scoped to a single user.

    user_id is captured by closure rather than exposed as a tool argument,
    so it can never be filled in or overridden by the LLM - the agent can
    only choose *which* analytics to request, never *whose*. To add a new
    capability for the agent, add another @tool function here (wrapping an
    AnalyticsService method) and include it in the returned list.
    """

    @tool
    def get_account_performance(days: int = 30) -> str:
        """Get account-level analytics: reach, impressions, profile visits,
        follower growth, and engagement rate over a lookback window.

        Use this for questions like "how did my account perform this week",
        "what is my engagement rate", or "show my follower growth".

        Args:
            days: Lookback window in days (1-365). Use 7 for "this week",
                30 for "this month", 90 for a quarter, etc.
        """
        try:
            result = analytics_service.get_account_analytics(user_id, days=days)
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return result.model_dump_json()

    @tool
    def get_media_performance(limit: int = 25, media_type: str | None = None) -> str:
        """Get analytics for individual posts and reels: likes, comments,
        shares, saves, reach, impressions, and engagement rate for each.

        Use this to inspect or list recent content performance.

        Args:
            limit: Maximum number of items to return (1-100).
            media_type: Optional filter - "IMAGE", "VIDEO", or "REELS".
        """
        try:
            results = analytics_service.get_media_analytics(user_id, limit=limit, media_type=media_type)
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return f"[{', '.join(item.model_dump_json() for item in results)}]"

    @tool
    def get_top_or_lowest_content(
        limit: int = 5,
        metric: str = "engagement_rate",
        order: str = "top",
        days: int | None = None,
    ) -> str:
        """Get the best- or worst-performing posts/reels, ranked by a metric,
        optionally restricted to posts published in a recent window.

        Use this for "which reel performed best", "which posts had the
        highest reach", "what's my worst-performing content", and
        time-scoped versions like "best post last month" (days=30).

        Args:
            limit: Maximum number of items to return (1-50).
            metric: One of "engagement_rate", "reach", "likes", "comments",
                "impressions".
            order: "top" for best-performing first, "bottom" for
                worst-performing first.
            days: Optional lookback window. When given, only posts published
                in the last N days are ranked. Omit to rank all stored posts.
        """
        if metric not in _VALID_METRICS:
            metric = "engagement_rate"
        if order not in _VALID_ORDERS:
            order = "top"
        try:
            result = analytics_service.get_top_content(
                user_id, limit=limit, metric=metric, order=order, days=days
            )
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return result.model_dump_json()

    @tool
    def get_performance_trends(granularity: str = "daily", days: int = 30) -> str:
        """Get historical performance bucketed by day, week, or month:
        reach, impressions, profile visits, follower count, posts published,
        and average engagement rate per bucket.

        Use this for growth-over-time questions and for comparing periods,
        e.g. "compare this month with last month" - request a wide enough
        window (e.g. days=60, granularity="monthly") and compare the buckets.

        Args:
            granularity: One of "daily", "weekly", "monthly".
            days: Lookback window in days (1-365).
        """
        if granularity not in _VALID_GRANULARITIES:
            granularity = "daily"
        try:
            result = analytics_service.get_trends(user_id, granularity=granularity, days=days)
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return result.model_dump_json()

    @tool
    def get_dashboard_summary() -> str:
        """Get a one-shot summary combining account analytics, top content,
        and a 7-day trend snapshot.

        Use this for broad requests like "summarize my recent performance"
        where the user hasn't asked about one specific metric.
        """
        try:
            result = analytics_service.get_dashboard(user_id)
        except InstagramAccountNotConnectedError:
            return NOT_CONNECTED_MESSAGE
        return result.model_dump_json()

    return [
        get_account_performance,
        get_media_performance,
        get_top_or_lowest_content,
        get_performance_trends,
        get_dashboard_summary,
    ]
