from collections import defaultdict
from typing import Any

from app.schemas.analytics import MediaAnalyticsResponse


def posting_time_breakdown(media_items: list[MediaAnalyticsResponse]) -> dict[str, Any]:
    """Average engagement rate grouped by hour-of-day and weekday.

    A real (if small-sample) statistical summary an LLM can narrate, rather
    than raw timestamps it would have to eyeball itself. sample_size lets
    the prompt (and the model) recognize when there's too little data to
    draw a real conclusion.
    """
    by_hour: dict[int, list[float]] = defaultdict(list)
    by_weekday: dict[str, list[float]] = defaultdict(list)

    for item in media_items:
        if item.posted_at is None or item.engagement_rate is None:
            continue
        by_hour[item.posted_at.hour].append(item.engagement_rate)
        by_weekday[item.posted_at.strftime("%A")].append(item.engagement_rate)

    return {
        "sample_size": sum(len(v) for v in by_hour.values()),
        "average_engagement_by_hour": {
            hour: round(sum(rates) / len(rates), 2) for hour, rates in sorted(by_hour.items())
        },
        "average_engagement_by_weekday": {
            day: round(sum(rates) / len(rates), 2) for day, rates in by_weekday.items()
        },
    }


def content_format_breakdown(media_items: list[MediaAnalyticsResponse]) -> dict[str, Any]:
    """Average engagement rate and post count grouped by media type."""
    by_type: dict[str, list[float]] = defaultdict(list)

    for item in media_items:
        if item.engagement_rate is not None:
            by_type[item.media_type].append(item.engagement_rate)

    return {
        media_type: {
            "average_engagement_rate": round(sum(rates) / len(rates), 2),
            "post_count": len(rates),
        }
        for media_type, rates in by_type.items()
    }


def posting_frequency(media_items: list[MediaAnalyticsResponse], window_days: int) -> dict[str, Any]:
    """Posts per week for items already filtered to the given window."""
    dated_count = sum(1 for item in media_items if item.posted_at is not None)
    posts_per_week = round(dated_count / (window_days / 7), 2) if dated_count and window_days > 0 else None

    return {
        "total_posts": dated_count,
        "window_days": window_days,
        "posts_per_week": posts_per_week,
    }


def content_summary(media_items: list[MediaAnalyticsResponse]) -> dict[str, Any]:
    """Aggregate post count, average engagement, and totals across a sample."""
    if not media_items:
        return {"post_count": 0}

    rates = [item.engagement_rate for item in media_items if item.engagement_rate is not None]
    return {
        "post_count": len(media_items),
        "average_engagement_rate": round(sum(rates) / len(rates), 2) if rates else None,
        "total_likes": sum(item.likes or 0 for item in media_items),
        "total_comments": sum(item.comments or 0 for item in media_items),
    }
