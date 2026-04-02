from __future__ import annotations

import logging
import sys
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    )
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def _access_logger() -> logging.Logger:
    return logging.getLogger("access")


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Request ID (X-Request-ID) and one access log line per request."""

    async def dispatch(self, request: Request, call_next):
        header_rid = request.headers.get("X-Request-ID")
        request_id = header_rid if header_rid else str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        user_id = getattr(request.state, "user_id", None)

        response.headers["X-Request-ID"] = request_id

        _access_logger().info(
            "http_access method=%s path=%s status=%s duration_ms=%s request_id=%s user_id=%s client=%s",
            request.method,
            request.url.path,
            response.status_code,
            round(duration_ms, 2),
            request_id,
            user_id if user_id is not None else "-",
            request.client.host if request.client else "-",
        )
        return response
