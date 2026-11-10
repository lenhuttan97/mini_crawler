"""SQLAlchemy runtime composition helpers."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap.settings import Settings
from app.platform.persistence.models import Base


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Build a session factory without connecting until a session is used."""
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def initialize_local_schema(settings: Settings) -> None:
    """Create local SQLite tables explicitly; broker mode still uses migrations."""
    if settings.runtime_mode == "broker":
        raise ValueError("local runtime mode is required to initialize local schema")
    engine = create_engine(settings.database_url, future=True)
    try:
        if engine.url.get_backend_name() != "sqlite":
            raise ValueError("local runtime requires a SQLite database")
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
