from datetime import datetime

import pytest

from app.schemas.analytics import MediaAnalyticsResponse
from app.utils.insight_calculations import (
    content_format_breakdown,
    posting_frequency,
    posting_time_breakdown,
)

pytestmark = pytest.mark.unit


def make_media(media_id="m", media_type="IMAGE", posted_at=None, engagement_rate=10.0):
    return MediaAnalyticsResponse(
        media_id=media_id,
        media_type=media_type,
        caption=None,
        permalink=None,
        posted_at=posted_at,
        likes=None,
        comments=None,
        shares=None,
        saves=None,
        reach=None,
        impressions=None,
        engagement_rate=engagement_rate,
        watch_time=None,
        completion_rate=None,
        insights_fetched_at=None,
    )


class TestPostingTimeBreakdown:
    def test_averages_engagement_by_hour_and_weekday(self):
        items = [
            # Both on a Wednesday at 09:00.
            make_media(posted_at=datetime(2026, 3, 18, 9, 0), engagement_rate=10.0),
            make_media(posted_at=datetime(2026, 3, 25, 9, 0), engagement_rate=20.0),
            make_media(posted_at=datetime(2026, 3, 19, 18, 0), engagement_rate=5.0),
        ]
        result = posting_time_breakdown(items)
        assert result["average_engagement_by_hour"][9] == 15.0
        assert result["average_engagement_by_hour"][18] == 5.0
        assert result["average_engagement_by_weekday"]["Wednesday"] == 15.0

    def test_reports_sample_size(self):
        """sample_size is what lets the prompt (and the model) tell a real
        pattern apart from one derived from a couple of posts."""
        items = [make_media(posted_at=datetime(2026, 3, 18, 9, 0))]
        assert posting_time_breakdown(items)["sample_size"] == 1

    def test_skips_items_without_a_timestamp_or_rate(self):
        items = [
            make_media(posted_at=None, engagement_rate=10.0),
            make_media(posted_at=datetime(2026, 3, 18, 9, 0), engagement_rate=None),
        ]
        result = posting_time_breakdown(items)
        assert result["sample_size"] == 0
        assert result["average_engagement_by_hour"] == {}

    def test_empty_input_is_handled(self):
        result = posting_time_breakdown([])
        assert result["sample_size"] == 0


class TestContentFormatBreakdown:
    def test_groups_by_media_type(self):
        items = [
            make_media(media_type="IMAGE", engagement_rate=10.0),
            make_media(media_type="IMAGE", engagement_rate=20.0),
            make_media(media_type="REELS", engagement_rate=30.0),
        ]
        result = content_format_breakdown(items)
        assert result["IMAGE"] == {"average_engagement_rate": 15.0, "post_count": 2}
        assert result["REELS"] == {"average_engagement_rate": 30.0, "post_count": 1}

    def test_excludes_items_without_a_rate(self):
        items = [make_media(media_type="IMAGE", engagement_rate=None)]
        assert content_format_breakdown(items) == {}


class TestPostingFrequency:
    def test_computes_posts_per_week(self):
        items = [make_media(posted_at=datetime(2026, 3, 18, 9, 0)) for _ in range(4)]
        result = posting_frequency(items, window_days=28)
        assert result["total_posts"] == 4
        assert result["posts_per_week"] == 1.0

    def test_ignores_items_without_a_timestamp(self):
        items = [make_media(posted_at=None), make_media(posted_at=datetime(2026, 3, 18))]
        assert posting_frequency(items, window_days=7)["total_posts"] == 1

    def test_no_posts_yields_none_rather_than_zero(self):
        """None means 'not enough history to say', which the prompt handles
        differently from a genuine zero."""
        assert posting_frequency([], window_days=30)["posts_per_week"] is None
