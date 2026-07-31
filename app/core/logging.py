import json
import logging
import sys
from datetime import datetime, timezone

from app.core.settings import settings

# Attribute names present on every stock LogRecord, computed from a throwaway
# instance rather than hardcoded so it stays correct across Python versions.
_RESERVED_RECORD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
}


class JSONFormatter(logging.Formatter):
    """Render each log record as a single JSON line.

    Any extra fields passed via `logger.info(..., extra={...})` are
    included as top-level keys, so callers can attach structured context
    (request_id, user_id, duration_ms, ...) without string formatting.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _RESERVED_RECORD_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Configure the root logger for structured (or plain-text) output.

    Called once at application startup, before any other module logs.
    """
    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.LOG_LEVEL)

    # These are noisy at INFO (every HTTP call to OpenAI/Instagram logs a
    # line) and duplicate what the request-logging middleware already
    # records at a more useful level of detail.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
