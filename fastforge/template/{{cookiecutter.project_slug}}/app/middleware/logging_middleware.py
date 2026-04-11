import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every request with correlation context."""

    SKIP_PATHS = {"/health", "/healthz", "/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        skip_logging = request.url.path in self.SKIP_PATHS
        logger = structlog.get_logger("http.request")

        if not skip_logging:
            await logger.ainfo("request_started")

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            await logger.aexception("request_failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        if not skip_logging:
            await logger.ainfo(
                "request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        structlog.contextvars.clear_contextvars()
        return response
