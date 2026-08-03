from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from app.models.deal import Deal
from app.repositories.deal_repository import DealRepository
from app.schemas.deals import (
    CurrencyEarnings,
    DealCreate,
    DealStatus,
    DealUpdate,
    EarningsPeriod,
    EarningsPeriodPoint,
    EarningsSummaryResponse,
    PaymentStatus,
)
from app.utils.analytics_calculations import bucket_start
from app.utils.ics import build_deal_ics


class DealServiceError(Exception):
    """Base class for deal service errors."""


class DealNotFoundError(DealServiceError):
    """Raised when no deal exists for this user with the given ID.

    Also raised for a deal that belongs to another user - the two cases are
    never distinguished, so a user can't enumerate other users' deal IDs by
    comparing error responses.
    """


class DealHasNoDatesError(DealServiceError):
    """Raised when a deal has neither a shoot date nor a payment due date to export."""


class DealService:
    """Coordinate persistence and derived views (earnings, calendar export) for deals."""

    def __init__(self, deal_repository: DealRepository) -> None:
        """Initialize the service with its repository dependency."""
        self.deal_repository = deal_repository

    def create_deal(self, user_id: int, payload: DealCreate) -> Deal:
        """Create a new deal for the given user."""
        deal = Deal(user_id=user_id, **payload.model_dump())
        created = self.deal_repository.create(deal)
        self._commit()
        return created

    def list_deals(
        self,
        user_id: int,
        deal_status: DealStatus | None = None,
        payment_status: PaymentStatus | None = None,
        shoot_from: date | None = None,
        shoot_to: date | None = None,
    ) -> list[Deal]:
        """List a user's deals, optionally filtered."""
        return self.deal_repository.list_by_user_id(
            user_id,
            deal_status=deal_status,
            payment_status=payment_status,
            shoot_from=shoot_from,
            shoot_to=shoot_to,
        )

    def get_deal(self, user_id: int, deal_id: int) -> Deal:
        """Return a single deal owned by the user, or raise DealNotFoundError."""
        deal = self.deal_repository.get_by_id(deal_id)
        if deal is None or deal.user_id != user_id:
            raise DealNotFoundError(f"No deal with ID {deal_id} was found.")
        return deal

    def update_deal(self, user_id: int, deal_id: int, payload: DealUpdate) -> Deal:
        """Replace every field of a deal owned by the user."""
        deal = self.get_deal(user_id, deal_id)
        for field, value in payload.model_dump().items():
            setattr(deal, field, value)
        self._commit()
        return deal

    def delete_deal(self, user_id: int, deal_id: int) -> None:
        """Delete a deal owned by the user."""
        deal = self.get_deal(user_id, deal_id)
        self.deal_repository.delete(deal.id)
        self._commit()

    def get_ics(self, user_id: int, deal_id: int) -> str:
        """Build a downloadable .ics calendar file for a deal's dates."""
        deal = self.get_deal(user_id, deal_id)
        try:
            return build_deal_ics(
                deal_id=deal.id,
                title=deal.title,
                brand_name=deal.brand_name,
                shoot_at=deal.shoot_at,
                payment_due_date=deal.payment_due_date,
                payment_amount=deal.payment_amount,
                currency=deal.currency,
            )
        except ValueError as exc:
            raise DealHasNoDatesError(str(exc)) from exc

    def get_earnings_summary(self, user_id: int, period: EarningsPeriod) -> EarningsSummaryResponse:
        """Summarize paid/pending totals per currency, bucketed by the given period."""
        deals = self.deal_repository.list_by_user_id(user_id)

        by_currency: dict[str, list[Deal]] = defaultdict(list)
        for deal in deals:
            by_currency[deal.currency].append(deal)

        excluded_undated_count = 0
        currencies: list[CurrencyEarnings] = []

        for currency, currency_deals in sorted(by_currency.items()):
            total_paid = Decimal("0")
            total_pending = Decimal("0")
            buckets: dict[date, list[Deal]] = defaultdict(list)

            for deal in currency_deals:
                amount = deal.payment_amount or Decimal("0")
                if deal.payment_status == "paid":
                    total_paid += amount
                else:
                    total_pending += amount

                bucket_moment = self._bucket_moment(deal)
                if bucket_moment is None:
                    excluded_undated_count += 1
                    continue
                buckets[bucket_start(bucket_moment, period)].append(deal)

            points = [
                self._summarize_bucket(period_start, bucket_deals)
                for period_start, bucket_deals in sorted(buckets.items())
            ]

            currencies.append(
                CurrencyEarnings(
                    currency=currency,
                    total_paid=total_paid,
                    total_pending=total_pending,
                    deals_counted=len(currency_deals),
                    points=points,
                )
            )

        return EarningsSummaryResponse(
            period=period,
            currencies=currencies,
            excluded_undated_count=excluded_undated_count,
        )

    @staticmethod
    def _bucket_moment(deal: Deal) -> datetime | None:
        if deal.shoot_at is not None:
            return deal.shoot_at
        if deal.payment_due_date is not None:
            return datetime.combine(deal.payment_due_date, datetime.min.time())
        return None

    @staticmethod
    def _summarize_bucket(period_start: date, deals: list[Deal]) -> EarningsPeriodPoint:
        paid_total = Decimal("0")
        pending_total = Decimal("0")
        for deal in deals:
            amount = deal.payment_amount or Decimal("0")
            if deal.payment_status == "paid":
                paid_total += amount
            else:
                pending_total += amount
        return EarningsPeriodPoint(
            period_start=period_start,
            paid_total=paid_total,
            pending_total=pending_total,
            deals_count=len(deals),
        )

    def _commit(self) -> None:
        self.deal_repository.db.commit()
