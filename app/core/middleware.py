import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_logger = logging.getLogger("app.request")

# Health/metrics endpoints are typically polled every few seconds by
# infrastructure and add pure noise to request logs.
_UNLOGGED_PATH_PREFIXES = ("/health", "/metrics")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request's method, path, status, and duration.

    Also stamps a request ID on the response (X-Request-ID) so a specific
    request can be traced from client report back to server logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
            return response
        finally:
            if not request.url.path.startswith(_UNLOGGED_PATH_PREFIXES):
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                request_logger.info(
                    "request completed",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code if response else 500,
                        "duration_ms": duration_ms,
                        "client_ip": request.client.host if request.client else None,
                    },
                )
            if response is not None:
                response.headers["X-Request-ID"] = request_id


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard defensive HTTP headers to every response."""

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
        # Only meaningful over HTTPS; harmless to send over plain HTTP too.
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in self._HEADERS.items():
            response.headers.setdefault(header, value)
        return response
