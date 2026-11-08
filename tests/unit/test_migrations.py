"""Tests for Alembic migrations (P01 Item 2).

Chạy offline trên SQLite file để xác định cấu trúc bảng và khả
năng upgrade/rollback mà không cần PostgreSQL thật.
"""

from __future__ import annotations

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.domain.models import Base


def _alembic_cfg(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


EXPECTED_TABLES = {
    "jobs",
    "audit_events",
    "crawl_jobs",
    "documents",
    "media_jobs",
    "media_job_items",
    "media_assets",
    "search_requests",
}


def _table_names(db_path: str) -> set[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    return {name for name in inspect(engine).get_table_names()}


def test_migrations_upgrade_creates_all_tables(tmp_path) -> None:
    """Alembic upgrade to head phải tạo toàn bộ bảng mô tả ở P01 §5.3."""
    db_path = str(tmp_path / "test.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    actual = _table_names(db_path)
    assert EXPECTED_TABLES <= actual, f"Thiếu bảng: {EXPECTED_TABLES - actual}"


def test_migrations_downgrade_removes_all_tables(tmp_path) -> None:
    """Alembic downgrade to base phải xóa toàn bộ bảng."""
    db_path = str(tmp_path / "test.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    actual = _table_names(db_path)
    assert not (EXPECTED_TABLES & actual), f"Vẫn còn bảng sau downgrade: {EXPECTED_TABLES & actual}"


def test_jobs_table_has_idempotency_unique_constraint(tmp_path) -> None:
    """Bảng jobs phải có unique constraint trên (caller_id, idempotency_key)."""
    db_path = str(tmp_path / "test.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    constraints = inspector.get_unique_constraints("jobs")
    assert any(
        set(constraint["column_names"]) == {"caller_id", "idempotency_key"}
        for constraint in constraints
    ), constraints


def test_migration_schema_matches_orm_metadata(tmp_path) -> None:
    """Alembic head phải có đúng bảng/cột mà ORM runtime sử dụng."""
    db_path = str(tmp_path / "parity.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")

    inspector = inspect(create_engine(f"sqlite:///{db_path}"))
    migration_schema = {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
        if table != "alembic_version"
    }
    model_schema = {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.sorted_tables
    }

    assert migration_schema == model_schema
