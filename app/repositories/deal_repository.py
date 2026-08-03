from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.repositories.base import BaseRepository


class DealRepository(BaseRepository[Deal]):
    """Handle persistence operations specific to deals."""

    def __init__(self, db: Session) -> None:
        """Initialize the deal repository."""
        super().__init__(Deal, db)

    def list_by_user_id(
        self,
        user_id: int,
        deal_status: str | None = None,
        payment_status: str | None = None,
        shoot_from: date | None = None,
        shoot_to: date | None = None,
    ) -> list[Deal]:
        """Return a user's deals, most recently shot first, optionally filtered."""
        statement = select(Deal).where(Deal.user_id == user_id)

        if deal_status is not None:
            statement = statement.where(Deal.deal_status == deal_status)
        if payment_status is not None:
            statement = statement.where(Deal.payment_status == payment_status)
        if shoot_from is not None:
            statement = statement.where(Deal.shoot_at >= shoot_from)
        if shoot_to is not None:
            statement = statement.where(Deal.shoot_at <= shoot_to)

        statement = statement.order_by(Deal.shoot_at.desc().nullslast(), Deal.id.desc())
        return list(self.db.scalars(statement).all())
