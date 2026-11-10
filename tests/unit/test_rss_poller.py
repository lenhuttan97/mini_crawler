"""RSS poller tests (P04 F02.6).

Chỉ poll RSS từ nguồn approved và đã bật feature rss.
Không tự download item, chỉ discovery và trả danh sách item đã chuẩn hóa.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.features.video_download.application.source_registry_service import SourceRegistryService
from app.legacy.rss.poller import RssPoller, RssPollError
from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base


def test_rss_poller_requires_approved_source_with_rss_feature(tmp_path) -> None:
    """Chỉ nguồn approved + feature rss mới được poll RSS."""
    engine = create_engine(f"sqlite:///{tmp_path / 'rss.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    registry = SourceRegistryService(session)
    registry.upsert(
        domain="no-rss.example",
        state=SourceStatus.APPROVED,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"rss": False},
    )
    registry.upsert(
        domain="rss.example",
        state=SourceStatus.APPROVED,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"rss": True},
    )
    session.commit()

    http_client = MagicMock()
    http_client.get.return_value.text = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>Item A</title><link>https://rss.example/a</link><pubDate>2026-11-08</pubDate></item>
    </channel></rss>"""

    poller = RssPoller(registry, http_client=http_client)

    # Không bật rss -> RssPollError
    try:
        poller.poll("no-rss.example", "https://no-rss.example/feed")
    except RssPollError:
        pass
    else:
        raise AssertionError("phải nêu RssPollError khi nguồn không bật rss")

    # Bật rss -> trả danh sách item đã chuẩn hóa
    result = poller.poll("rss.example", "https://rss.example/feed")
    assert len(result) == 1
    assert result[0]["title"] == "Item A"
    assert result[0]["link"] == "https://rss.example/a"
    assert result[0]["source"] == "rss.example"
    http_client.get.assert_called_once_with("https://rss.example/feed")

    # Nguồn unknown -> RssPollError
    try:
        poller.poll("unknown.example", "https://unknown.example/feed")
    except RssPollError:
        pass
    else:
        raise AssertionError("phải nêu RssPollError khi nguồn không đăng ký")
