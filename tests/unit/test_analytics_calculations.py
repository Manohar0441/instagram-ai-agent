from datetime import date, datetime, timezone

import pytest

from app.utils.analytics_calculations import (
    as_aware_utc,
    average_or_none,
    bucket_start,
    calculate_engagement_rate,
    calculate_growth,
    rank_content,
    sum_or_none,
)

pytestmark = pytest.mark.unit


class TestCalculateEngagementRate:
    def test_uses_reach_as_denominator(self):
        assert calculate_engagement_rate(50, reach=1000) == 5.0

    def test_falls_back_to_followers_when_reach_missing(self):
        assert calculate_engagement_rate(50, reach=None, followers=500) == 10.0

    def test_prefers_reach_over_followers(self):
        assert calculate_engagement_rate(50, reach=1000, followers=100) == 5.0

    def test_returns_none_without_a_denominator(self):
        assert calculate_engagement_rate(50) is None

    @pytest.mark.parametrize("denominator", [0, None])
    def test_never_divides_by_zero_or_none(self, denominator):
        """A zero denominator must yield None, not raise or produce infinity."""
        assert calculate_engagement_rate(50, reach=denominator) is None

    def test_rounds_to_two_decimals(self):
        assert calculate_engagement_rate(1, reach=3) == 33.33


class TestCalculateGrowth:
    def test_computes_absolute_and_percentage(self):
        growth = calculate_growth(1000, 1200)
        assert growth.absolute == 200
        assert growth.percentage == 20.0

    def test_handles_negative_growth(self):
        growth = calculate_growth(1000, 900)
        assert growth.absolute == -100
        assert growth.percentage == -10.0

    def test_returns_none_when_either_value_missing(self):
        assert calculate_growth(None, 100) is None
        assert calculate_growth(100, None) is None

    def test_percentage_is_none_when_starting_from_zero(self):
        """Growth from zero has no meaningful percentage, but the absolute still does."""
        growth = calculate_growth(0, 50)
        assert growth.absolute == 50
        assert growth.percentage is None


class TestBucketStart:
    def test_daily_bucket_is_the_day_itself(self):
        moment = datetime(2026, 3, 18, 14, 30, tzinfo=timezone.utc)
        assert bucket_start(moment, "daily") == date(2026, 3, 18)

    def test_weekly_bucket_snaps_back_to_monday(self):
        # 2026-03-18 is a Wednesday.
        moment = datetime(2026, 3, 18, 14, 30, tzinfo=timezone.utc)
        assert bucket_start(moment, "weekly") == date(2026, 3, 16)

    def test_weekly_bucket_of_a_monday_is_that_monday(self):
        moment = datetime(2026, 3, 16, 0, 0, tzinfo=timezone.utc)
        assert bucket_start(moment, "weekly") == date(2026, 3, 16)

    def test_monthly_bucket_snaps_to_first_of_month(self):
        moment = datetime(2026, 3, 18, 14, 30, tzinfo=timezone.utc)
        assert bucket_start(moment, "monthly") == date(2026, 3, 1)


class TestAggregationHelpers:
    def test_sum_or_none_sums_values(self):
        assert sum_or_none([1, 2, 3]) == 6

    def test_sum_or_none_returns_none_for_empty(self):
        """Empty means 'no data', which must not be reported as a real zero."""
        assert sum_or_none([]) is None

    def test_average_or_none_averages_and_rounds(self):
        assert average_or_none([1.0, 2.0]) == 1.5
        assert average_or_none([1.0, 2.0, 2.0]) == 1.67

    def test_average_or_none_returns_none_for_empty(self):
        assert average_or_none([]) is None


class TestRankContent:
    class Item:
        def __init__(self, name, score):
            self.name = name
            self.score = score

    def _items(self):
        return [self.Item("a", 5.0), self.Item("b", 15.0), self.Item("c", 10.0)]

    def test_top_order_is_highest_first(self):
        ranked = rank_content(self._items(), lambda i: i.score, "top", 3)
        assert [i.name for i in ranked] == ["b", "c", "a"]

    def test_bottom_order_is_lowest_first(self):
        ranked = rank_content(self._items(), lambda i: i.score, "bottom", 3)
        assert [i.name for i in ranked] == ["a", "c", "b"]

    def test_respects_limit(self):
        ranked = rank_content(self._items(), lambda i: i.score, "top", 2)
        assert len(ranked) == 2

    def test_excludes_items_with_no_score(self):
        """An item with no computable metric can't be judged best or worst,
        so it is dropped rather than treated as a zero."""
        items = self._items() + [self.Item("d", None)]
        ranked = rank_content(items, lambda i: i.score, "bottom", 10)
        assert "d" not in [i.name for i in ranked]
        assert len(ranked) == 3

    def test_empty_input_gives_empty_output(self):
        assert rank_content([], lambda i: i.score, "top", 5) == []


class TestAsAwareUtc:
    def test_naive_datetime_is_treated_as_utc(self):
        naive = datetime(2026, 3, 18, 12, 0)
        assert as_aware_utc(naive).tzinfo == timezone.utc

    def test_aware_datetime_is_left_alone(self):
        aware = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
        assert as_aware_utc(aware) is aware
