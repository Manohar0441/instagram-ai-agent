from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.repositories.deal_repository import DealRepository
from app.schemas.deals import DealCreate, DealUpdate
from app.services.deals_service import DealHasNoDatesError, DealNotFoundError, DealService

pytestmark = pytest.mark.integration


@pytest.fixture
def deal_service(db):
    return DealService(DealRepository(db))


class TestCreateAndGetDeal:
    def test_creates_and_retrieves_a_deal(self, deal_service, db_user):
        deal = deal_service.create_deal(
            db_user.id,
            DealCreate(title="Reel Campaign", brand_name="Acme", payment_amount=Decimal("5000")),
        )
        fetched = deal_service.get_deal(db_user.id, deal.id)
        assert fetched.title == "Reel Campaign"
        assert fetched.brand_name == "Acme"
        assert fetched.payment_amount == Decimal("5000")
        assert fetched.currency == "INR"
        assert fetched.deal_status == "negotiating"
        assert fetched.payment_status == "unpaid"

    def test_raises_for_a_missing_deal(self, deal_service, db_user):
        with pytest.raises(DealNotFoundError):
            deal_service.get_deal(db_user.id, 999)


class TestUpdateDeal:
    def test_replaces_every_field(self, deal_service, db_user):
        deal = deal_service.create_deal(
            db_user.id, DealCreate(title="Reel", brand_name="Acme")
        )
        updated = deal_service.update_deal(
            db_user.id,
            deal.id,
            DealUpdate(
                title="Updated Reel",
                brand_name="Acme",
                deal_status="completed",
                payment_status="paid",
                payment_amount=Decimal("7500"),
            ),
        )
        assert updated.title == "Updated Reel"
        assert updated.deal_status == "completed"
        assert updated.payment_status == "paid"
        assert updated.payment_amount == Decimal("7500")


class TestDeleteDeal:
    def test_removes_the_deal(self, deal_service, db_user):
        deal = deal_service.create_deal(
            db_user.id, DealCreate(title="Reel", brand_name="Acme")
        )
        deal_service.delete_deal(db_user.id, deal.id)
        with pytest.raises(DealNotFoundError):
            deal_service.get_deal(db_user.id, deal.id)


class TestCrossUserIsolation:
    """A deal belonging to another user must be indistinguishable from a missing one."""

    def test_get_raises_not_found_for_another_users_deal(self, deal_service, db, db_user):
        from app.models.user import User
        from app.utils.security import hash_password

        other = User(
            username="other2", full_name="Other Two",
            email="other2@example.com", hashed_password=hash_password("supersecret123"),
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        deal = deal_service.create_deal(other.id, DealCreate(title="Reel", brand_name="Acme"))

        with pytest.raises(DealNotFoundError):
            deal_service.get_deal(db_user.id, deal.id)

    def test_update_raises_not_found_for_another_users_deal(self, deal_service, db, db_user):
        from app.models.user import User
        from app.utils.security import hash_password

        other = User(
            username="other3", full_name="Other Three",
            email="other3@example.com", hashed_password=hash_password("supersecret123"),
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        deal = deal_service.create_deal(other.id, DealCreate(title="Reel", brand_name="Acme"))

        with pytest.raises(DealNotFoundError):
            deal_service.update_deal(
                db_user.id, deal.id, DealUpdate(title="Hijacked", brand_name="Acme")
            )


class TestGetIcs:
    def test_raises_when_neither_date_is_set(self, deal_service, db_user):
        deal = deal_service.create_deal(db_user.id, DealCreate(title="Reel", brand_name="Acme"))
        with pytest.raises(DealHasNoDatesError):
            deal_service.get_ics(db_user.id, deal.id)

    def test_returns_ics_text_when_a_date_is_set(self, deal_service, db_user):
        deal = deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="Reel",
                brand_name="Acme",
                shoot_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            ),
        )
        ics_text = deal_service.get_ics(db_user.id, deal.id)
        assert "BEGIN:VCALENDAR" in ics_text


class TestEarningsSummary:
    def test_groups_totals_by_currency_and_never_mixes_them(self, deal_service, db_user):
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="INR deal", brand_name="Acme", currency="INR",
                payment_amount=Decimal("1000"), payment_status="paid",
                shoot_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            ),
        )
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="USD deal", brand_name="Globex", currency="USD",
                payment_amount=Decimal("100"), payment_status="unpaid",
                shoot_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
            ),
        )

        summary = deal_service.get_earnings_summary(db_user.id, "monthly")
        by_currency = {c.currency: c for c in summary.currencies}

        assert by_currency["INR"].total_paid == Decimal("1000")
        assert by_currency["INR"].total_pending == Decimal("0")
        assert by_currency["USD"].total_paid == Decimal("0")
        assert by_currency["USD"].total_pending == Decimal("100")

    def test_partial_status_counts_as_pending(self, deal_service, db_user):
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="Partly paid", brand_name="Acme", payment_amount=Decimal("2000"),
                payment_status="partial", shoot_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            ),
        )
        summary = deal_service.get_earnings_summary(db_user.id, "monthly")
        assert summary.currencies[0].total_pending == Decimal("2000")
        assert summary.currencies[0].total_paid == Decimal("0")

    def test_undated_deal_is_excluded_from_points_but_counted_in_totals(
        self, deal_service, db_user
    ):
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="Undated", brand_name="Acme", payment_amount=Decimal("500"),
                payment_status="paid",
            ),
        )
        summary = deal_service.get_earnings_summary(db_user.id, "monthly")
        assert summary.excluded_undated_count == 1
        assert summary.currencies[0].points == []
        assert summary.currencies[0].total_paid == Decimal("500")

    def test_deal_with_no_amount_counts_toward_deals_count_only(self, deal_service, db_user):
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="Negotiating", brand_name="Acme",
                shoot_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            ),
        )
        summary = deal_service.get_earnings_summary(db_user.id, "monthly")
        currency = summary.currencies[0]
        assert currency.deals_counted == 1
        assert currency.total_paid == Decimal("0")
        assert currency.total_pending == Decimal("0")
        assert currency.points[0].deals_count == 1

    def test_buckets_by_the_requested_period(self, deal_service, db_user):
        deal_service.create_deal(
            db_user.id,
            DealCreate(
                title="June deal", brand_name="Acme", payment_amount=Decimal("100"),
                payment_status="paid", shoot_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
            ),
        )
        summary = deal_service.get_earnings_summary(db_user.id, "yearly")
        assert summary.currencies[0].points[0].period_start == date(2026, 1, 1)
