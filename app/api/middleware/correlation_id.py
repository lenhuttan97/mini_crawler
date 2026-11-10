"""Correlation ID middleware (P00 Items 3 and 6).

Reads or generates an X-Request-ID header, echoes it on the response, and
binds it to the logging context for the duration of the request.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.platform.observability.logging import bind_correlation_id, clear_correlation_id

HEADER_NAME = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that propagates a correlation ID across a request."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        correlation_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())
        bind_correlation_id(correlation_id)
        try:
            response = await call_next(request)
        finally:
            clear_correlation_id()
        response.headers[HEADER_NAME] = correlation_id
        return response
