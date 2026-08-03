from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Deal(Base):
    """A brand collaboration or content-creation gig, tracked for income and scheduling."""

    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliverables: Mapped[str | None] = mapped_column(Text, nullable=True)

    deal_status: Mapped[str] = mapped_column(
        String(20),
        server_default="negotiating",
        nullable=False,
    )

    # Keeps a time component - a shoot is usually a call time, not just a day.
    shoot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), server_default="INR", nullable=False)

    payment_status: Mapped[str] = mapped_column(
        String(10),
        server_default="unpaid",
        nullable=False,
    )

    payment_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
