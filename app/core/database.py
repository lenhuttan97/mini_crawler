"""SQLAlchemy runtime composition helpers."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Build a session factory without connecting until a session is used."""
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
