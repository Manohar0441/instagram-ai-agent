import logging

from fastapi import Request
from fastapi.responses import JSONResponse

error_logger = logging.getLogger("app.errors")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log the full exception server-side; return a generic message to the client.

    FastAPI's default handler already avoids leaking tracebacks to clients
    (with debug=False, which this app never overrides), but leaves failures
    unlogged. This makes both guarantees explicit and centralizes them, so
    every unhandled exception - regardless of route - is both logged with
    full context and answered with the same sanitized response.
    """
    error_logger.error(
        "unhandled exception",
        exc_info=exc,
        extra={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )
