from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.utils.ics import build_deal_ics

pytestmark = pytest.mark.unit


class TestBuildDealIcs:
    def test_raises_when_neither_date_is_set(self):
        with pytest.raises(ValueError):
            build_deal_ics(
                deal_id=1,
                title="Reel",
                brand_name="Acme",
                shoot_at=None,
                payment_due_date=None,
                payment_amount=None,
                currency="INR",
            )

    def test_shoot_only_produces_one_vevent(self):
        text = build_deal_ics(
            deal_id=1,
            title="Reel",
            brand_name="Acme",
            shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            payment_due_date=None,
            payment_amount=None,
            currency="INR",
        )
        assert text.count("BEGIN:VEVENT") == 1
        assert "deal-1-shoot@instalysis" in text
        assert "DTSTART:20260901T100000Z" in text
        assert "TRIGGER:-PT1H" in text

    def test_due_date_only_produces_one_all_day_vevent(self):
        text = build_deal_ics(
            deal_id=2,
            title="Reel",
            brand_name="Acme",
            shoot_at=None,
            payment_due_date=date(2026, 9, 15),
            payment_amount=Decimal("15000.00"),
            currency="INR",
        )
        assert text.count("BEGIN:VEVENT") == 1
        assert "deal-2-payment@instalysis" in text
        assert "DTSTART;VALUE=DATE:20260915" in text
        assert "TRIGGER:-P1D" in text
        assert "15000.00 INR" in text

    def test_both_dates_produce_two_vevents(self):
        text = build_deal_ics(
            deal_id=3,
            title="Reel",
            brand_name="Acme",
            shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            payment_due_date=date(2026, 9, 15),
            payment_amount=None,
            currency="INR",
        )
        assert text.count("BEGIN:VEVENT") == 2

    def test_payment_summary_omits_amount_when_unknown(self):
        text = build_deal_ics(
            deal_id=4,
            title="Reel",
            brand_name="Acme",
            shoot_at=None,
            payment_due_date=date(2026, 9, 15),
            payment_amount=None,
            currency="INR",
        )
        assert "INR" not in text.split("SUMMARY:")[1]

    def test_special_characters_are_escaped(self):
        text = build_deal_ics(
            deal_id=5,
            title="Reel, Part 1; Take 2\nRetake",
            brand_name="Acme",
            shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            payment_due_date=None,
            payment_amount=None,
            currency="INR",
        )
        summary_line = next(line for line in text.split("\r\n") if line.startswith("SUMMARY:"))
        assert "\\," in summary_line
        assert "\\;" in summary_line
        assert "\\n" in summary_line
        # Real (unescaped) newlines/semicolons/commas must not survive in the field value.
        assert "\n" not in summary_line

    def test_uses_crlf_line_endings(self):
        text = build_deal_ics(
            deal_id=6,
            title="Reel",
            brand_name="Acme",
            shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            payment_due_date=None,
            payment_amount=None,
            currency="INR",
        )
        assert "\r\n" in text
        assert text.startswith("BEGIN:VCALENDAR\r\n")
