from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DealStatus = Literal["negotiating", "confirmed", "completed", "cancelled"]
PaymentStatus = Literal["unpaid", "partial", "paid"]
EarningsPeriod = Literal["weekly", "monthly", "yearly"]


class DealCreate(BaseModel):
    """Fields required to log a new brand collaboration or content-creation gig."""

    title: str = Field(min_length=1, max_length=200)
    brand_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    deliverables: str | None = None
    deal_status: DealStatus = "negotiating"
    shoot_at: datetime | None = None
    payment_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    payment_status: PaymentStatus = "unpaid"
    payment_due_date: date | None = None
    work_link: str | None = Field(default=None, max_length=2048)
    notes: str | None = None


class DealUpdate(BaseModel):
    """Full replacement payload for an existing deal - every field, same shape as DealCreate."""

    title: str = Field(min_length=1, max_length=200)
    brand_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    deliverables: str | None = None
    deal_status: DealStatus = "negotiating"
    shoot_at: datetime | None = None
    payment_amount: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    payment_status: PaymentStatus = "unpaid"
    payment_due_date: date | None = None
    work_link: str | None = Field(default=None, max_length=2048)
    notes: str | None = None


class DealResponse(BaseModel):
    """A stored deal, as returned by the API."""

    id: int
    title: str
    brand_name: str
    description: str | None
    deliverables: str | None
    deal_status: DealStatus
    shoot_at: datetime | None
    payment_amount: Decimal | None
    currency: str
    payment_status: PaymentStatus
    payment_due_date: date | None
    work_link: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EarningsPeriodPoint(BaseModel):
    """Paid and pending totals for a single time bucket in an earnings summary."""

    period_start: date
    paid_total: Decimal
    pending_total: Decimal
    deals_count: int


class CurrencyEarnings(BaseModel):
    """Earnings summary for a single currency - amounts are never mixed across currencies."""

    currency: str
    total_paid: Decimal
    total_pending: Decimal
    deals_counted: int
    points: list[EarningsPeriodPoint]


class EarningsSummaryResponse(BaseModel):
    """Income summary across all of a user's deals, grouped by currency and time bucket."""

    period: EarningsPeriod
    currencies: list[CurrencyEarnings]
    # Deals with neither a shoot date nor a payment due date can't be placed
    # in a time bucket, but are still counted in each currency's totals - this
    # is how many were left out of `points` specifically.
    excluded_undated_count: int
