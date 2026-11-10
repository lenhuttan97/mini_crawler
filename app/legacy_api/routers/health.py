"""Health check routers (P00 Item 3)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health/live", summary="Liveness probe")
async def live() -> dict[str, str]:
    """Return liveness status. No config, secret, or upstream detail is leaked."""
    return {"status": "live"}


@router.get("/health/ready", summary="Readiness probe")
async def ready() -> dict[str, str]:
    """Return readiness status. No config, secret, or upstream detail is leaked."""
    return {"status": "ready"}
