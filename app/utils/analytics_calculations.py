from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal, TypeVar

T = TypeVar("T")

Granularity = Literal["daily", "weekly", "monthly"]
RankOrder = Literal["top", "bottom"]


def calculate_engagement_rate(
    engagements: int,
    reach: int | None = None,
    followers: int | None = None,
) -> float | None:
    """Engagement rate as a percentage of reach (falling back to followers).

    Returns None when neither denominator is available, rather than
    dividing by zero or fabricating a rate from incomplete data.
    """
    denominator = reach or followers
    if not denominator:
        return None
    return round((engagements / denominator) * 100, 2)


@dataclass
class Growth:
    """Absolute and percentage change between two point-in-time values."""

    absolute: int
    percentage: float | None


def calculate_growth(previous: int | None, current: int | None) -> Growth | None:
    """Compute growth between two snapshots, or None if either is missing."""
    if previous is None or current is None:
        return None
    absolute = current - previous
    percentage = round((absolute / previous) * 100, 2) if previous else None
    return Growth(absolute=absolute, percentage=percentage)


def as_aware_utc(moment: datetime) -> datetime:
    """Treat a naive datetime as UTC (some backends drop tzinfo on round-trip)."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def bucket_start(moment: datetime, granularity: Granularity) -> date:
    """Return the start-of-bucket date for a timestamp at the given granularity."""
    day = moment.date()
    if granularity == "daily":
        return day
    if granularity == "weekly":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def sum_or_none(values: list[int]) -> int | None:
    """Sum additive counts (e.g. reach), or None if there's nothing to sum."""
    if not values:
        return None
    return sum(values)


def average_or_none(values: list[float]) -> float | None:
    """Average rate-like values (e.g. engagement rate), or None if empty."""
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def rank_content(
    items: Iterable[T],
    key_func: Callable[[T], float | None],
    order: RankOrder,
    limit: int,
) -> list[T]:
    """Rank items by a numeric key, dropping items with no computable value.

    An item with no value can't fairly be judged best or worst performing,
    so it's excluded from the ranking entirely rather than defaulting to 0.
    """
    ranked = [item for item in items if key_func(item) is not None]
    ranked.sort(key=key_func, reverse=(order == "top"))
    return ranked[:limit]
