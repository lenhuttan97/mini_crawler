"""Tests for the explicit local SQLite schema bootstrap."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect

from app.bootstrap.database import initialize_local_schema
from app.bootstrap.settings import Settings


def test_initialize_local_schema_creates_job_and_document_tables(tmp_path) -> None:
    """Local bootstrap creates the durable tables used by crawl/media execution."""
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'local.db'}", runtime_mode="inline")

    initialize_local_schema(settings)

    engine = create_engine(settings.database_url)
    try:
        assert inspect(engine).has_table("jobs")
        assert inspect(engine).has_table("documents")
    finally:
        engine.dispose()


def test_initialize_local_schema_rejects_broker_mode(tmp_path) -> None:
    """Broker mode must use migrations, not implicit local schema creation."""
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'local.db'}")

    with pytest.raises(ValueError, match="local runtime"):
        initialize_local_schema(settings)
