import logging
import time

from botocore.exceptions import ClientError
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.settings import settings
from app.database.session import SessionLocal
from app.integrations.dynamodb_client import get_cache_table

logger = logging.getLogger("app.health")

router = APIRouter(tags=["Health"])

_START_TIME = time.monotonic()


@router.get(
    "/health/live",
    summary="Liveness check",
    description="Is the process alive and responsive? No external dependencies are checked - "
    "a failure here means the process itself should be restarted.",
)
def liveness() -> dict:
    """Trivial liveness probe: if this handler runs at all, the process is alive."""
    return {"status": "alive"}


@router.get(
    "/health/ready",
    summary="Readiness check",
    description="Can this instance serve traffic? Checks database and cache-table connectivity.",
)
def readiness(response: Response) -> dict:
    """Readiness probe: verifies the dependencies this app needs to actually serve requests."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    is_ready = all(checks.values())
    response.status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ready" if is_ready else "not_ready", "checks": checks}


@router.get(
    "/health",
    summary="Application health check",
    description="General health summary: app info, uptime, and dependency status.",
)
def health(response: Response) -> dict:
    """General health summary combining app metadata with dependency checks."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    is_healthy = all(checks.values())
    response.status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "healthy" if is_healthy else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 2),
        "checks": checks,
    }


def _check_database() -> bool:
    # Deliberately catches any exception: a health check must never itself
    # raise, regardless of what kind of failure the dependency produces.
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception:
        return False


def _check_cache() -> bool:
    try:
        get_cache_table().get_item(Key={"cache_key": "__health_check__"})
        return True
    except ClientError as exc:
        logger.warning("cache readiness check failed", extra={"error": str(exc)})
        return False
