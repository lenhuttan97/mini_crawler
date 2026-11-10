"""Tests for worker v1 additive Alembic migration (P01 Item 2).

Runs offline on SQLite to verify structure and rollback without a real
PostgreSQL. Legacy tables are untouched; only the v1 tables are added/removed.
"""

from __future__ import annotations

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def _alembic_cfg(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


EXPECTED_V1_TABLES = {
    "feature_jobs",
    "job_commands",
    "outbox_events",
    "job_leases",
    "workflow_runs",
    "workflow_steps",
    "search_result_sets",
}


def _table_names(db_path: str) -> set[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    return {name for name in inspect(engine).get_table_names()}


def test_migration_upgrade_creates_v1_tables(tmp_path) -> None:
    """Alembic upgrade to head creates legacy and worker v1 tables."""
    db_path = str(tmp_path / "v1.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    actual = _table_names(db_path)
    assert EXPECTED_V1_TABLES <= actual, f"Thiếu bảng v1: {EXPECTED_V1_TABLES - actual}"


def test_migration_downgrade_removes_v1_tables_only(tmp_path) -> None:
    """Downgrade to base removes v1 tables and legacy tables alike."""
    db_path = str(tmp_path / "v1.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    actual = _table_names(db_path)
    assert not (EXPECTED_V1_TABLES & actual), f"Vẫn còn bảng v1: {EXPECTED_V1_TABLES & actual}"


def test_feature_jobs_has_idempotency_unique_constraint(tmp_path) -> None:
    """Feature jobs must be unique on (idempotency_scope, idempotency_key)."""
    db_path = str(tmp_path / "v1.db")
    cfg = _alembic_cfg(db_path)
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    constraints = inspector.get_unique_constraints("feature_jobs")
    assert any(
        set(constraint["column_names"]) == {"idempotency_scope", "idempotency_key"}
        for constraint in constraints
    ), constraints
