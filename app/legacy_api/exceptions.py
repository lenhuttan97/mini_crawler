"""Consistent JSON error envelope for API exceptions (P00 Item 3)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a consistent JSON error envelope for HTTP exceptions."""
    from fastapi.exceptions import HTTPException

    assert isinstance(exc, HTTPException)  # narrowed for type checkers
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail if isinstance(exc.detail, str) else "error",
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a consistent JSON error envelope for unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "internal server error",
        },
    )
