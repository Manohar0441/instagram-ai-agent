from typing import Any, Literal

from app.database.session import SessionLocal
from app.repositories.account_insight_repository import AccountInsightRepository
from app.repositories.instagram_account_repository import InstagramAccountRepository
from app.repositories.instagram_media_repository import InstagramMediaRepository
from app.repositories.media_insight_repository import MediaInsightRepository
from app.services.analytics_service import AnalyticsService
from app.services.report_service import ReportService


def generate_report_job(user_id: int, period: Literal["weekly", "monthly"]) -> dict[str, Any]:
    """Generate an AI performance report in the background.

    RQ workers run in a separate process with no FastAPI request context,
    so this builds its own DB session and service graph directly rather
    than using the app/dependencies DI functions (which require Depends()).
    The result is returned as a plain JSON-serializable dict, since RQ
    pickles job results and Pydantic models aren't guaranteed picklable
    across process/version boundaries.
    """
    db = SessionLocal()
    try:
        analytics_service = AnalyticsService(
            InstagramAccountRepository(db),
            InstagramMediaRepository(db),
            MediaInsightRepository(db),
            AccountInsightRepository(db),
        )
        report_service = ReportService(analytics_service)
        report = report_service.generate_report(user_id, period=period)
        return report.model_dump(mode="json")
    finally:
        db.close()
