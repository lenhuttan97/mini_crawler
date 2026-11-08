"""Runtime database composition tests (P00/P02)."""

from __future__ import annotations

from sqlalchemy import text

from app.core.settings import Settings


def test_session_factory_uses_configured_database_url(tmp_path) -> None:
    """A factory creates sessions against the injected database URL on demand."""
    from app.core.database import create_session_factory

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runtime.db'}")
    session_factory = create_session_factory(settings)

    with session_factory() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1
