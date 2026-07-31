from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_insight import AccountInsight
from app.repositories.base import BaseRepository


class AccountInsightRepository(BaseRepository[AccountInsight]):
    """Handle persistence operations specific to account insight snapshots."""

    def __init__(self, db: Session) -> None:
        """Initialize the account insight repository."""
        super().__init__(AccountInsight, db)

    def create_snapshot(
        self, instagram_account_id: int, period: str, metrics: dict
    ) -> AccountInsight:
        """Persist a new insight metrics snapshot for a connected account."""
        return self.create(
            AccountInsight(
                instagram_account_id=instagram_account_id,
                period=period,
                metrics=metrics,
            )
        )

    def get_latest_by_account_id(
        self, instagram_account_id: int, period: str
    ) -> AccountInsight | None:
        """Return the most recent insight snapshot for an account/period, if any."""
        statement = (
            select(AccountInsight)
            .where(
                AccountInsight.instagram_account_id == instagram_account_id,
                AccountInsight.period == period,
            )
            .order_by(AccountInsight.fetched_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_by_account_id(
        self,
        instagram_account_id: int,
        period: str | None = None,
        since: datetime | None = None,
    ) -> list[AccountInsight]:
        """Return insight snapshots for an account, oldest first."""
        conditions = [AccountInsight.instagram_account_id == instagram_account_id]
        if period is not None:
            conditions.append(AccountInsight.period == period)
        if since is not None:
            conditions.append(AccountInsight.fetched_at >= since)

        statement = (
            select(AccountInsight)
            .where(*conditions)
            .order_by(AccountInsight.fetched_at.asc())
        )
        return list(self.db.scalars(statement).all())
