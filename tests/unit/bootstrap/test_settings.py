"""Tests for application settings (P00 Item 2)."""

from __future__ import annotations

from importlib import import_module

import pytest


def _import_settings():
    return import_module("app.bootstrap.settings")


def test_settings_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings should read values from environment variables."""
    monkeypatch.setenv("APP_PROFILE", "local")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("APP_PORT", "8000")

    settings = _import_settings().Settings()
    assert settings.profile == "local"
    assert settings.secret_key.get_secret_value() == "test-secret-key"
    assert settings.port == 8000


def test_settings_production_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production profile must fail fast when a required secret is missing."""
    monkeypatch.setenv("APP_PROFILE", "prod")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        _import_settings().Settings()


def test_settings_applies_profile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local/test profiles should apply sensible defaults without secrets."""
    monkeypatch.setenv("APP_PROFILE", "test")
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key")

    settings = _import_settings().Settings()
    assert settings.profile == "test"
    assert settings.debug is True


def test_settings_loads_compose_infrastructure_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compose service URLs must be represented by typed runtime settings."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/crawler")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minio-access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minio-secret")
    monkeypatch.setenv("SEARXNG_URL", "http://searxng:8080")

    settings = _import_settings().Settings()

    assert settings.database_url == "postgresql+psycopg://user:pass@postgres:5432/crawler"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.minio_endpoint == "http://minio:9000"
    assert settings.minio_access_key.get_secret_value() == "minio-access"
    assert settings.minio_secret_key.get_secret_value() == "minio-secret"
    assert settings.searxng_url == "http://searxng:8080"
