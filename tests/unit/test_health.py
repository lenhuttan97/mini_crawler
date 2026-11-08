"""Tests for API health endpoints (P00 Item 3)."""

from __future__ import annotations

from importlib import import_module


def _import_app():
    return import_module("app.api.main")


def test_health_live() -> None:
    """GET /health/live must return a live status envelope."""
    app = _import_app().create_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "live"}


def test_health_ready() -> None:
    """GET /health/ready must return a ready envelope without secrets."""
    app = _import_app().create_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "secret" not in str(body).lower()


def test_error_envelope() -> None:
    """Unknown routes must return a consistent JSON error envelope."""
    app = _import_app().create_app()
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/no-such-endpoint")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert "message" in body


def test_openapi_metadata() -> None:
    """OpenAPI metadata (title/version) must be present."""
    app = _import_app().create_app()
    assert app.title == "Mini Crawler"
    assert app.version == "0.1.0"


def test_app_exposes_injected_runtime_settings() -> None:
    """Routes must share the explicit Settings instance used to build the application."""
    from app.core.settings import Settings

    settings = Settings(profile="test")
    app = _import_app().create_app(settings)

    assert app.state.settings is settings
