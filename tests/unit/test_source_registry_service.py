"""Durable approved-source and feature-flag tests (P04)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base


def test_durable_registry_requires_approved_source_and_enabled_feature(tmp_path) -> None:
    """Video/torrent/RSS network work is deny-by-default per persisted source flag."""
    from app.features.video_download.application.source_registry_service import SourceRegistryService

    engine = create_engine(f"sqlite:///{tmp_path / 'sources.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    service = SourceRegistryService(session)

    service.upsert(
        domain="media.example",
        state=SourceStatus.APPROVED,
        owner="rights-team",
        distribution_evidence="license-2026-01",
        feature_flags={"video": True, "rss": True, "torrent": False},
    )
    session.commit()

    assert service.allows_network(domain="media.example", feature="video") is True
    assert service.allows_network(domain="media.example", feature="rss") is True
    assert service.allows_network(domain="media.example", feature="torrent") is False
    assert service.allows_network(domain="unknown.example", feature="rss") is False
