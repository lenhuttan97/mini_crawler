"""Video discovery service tests (P04 F02.2).

Chỉ discover video từ nguồn approved và đã bật feature video.
Không gọi mạng thật, không download video.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.enums import SourceStatus
from app.platform.persistence.models import Base
from app.services.video_discovery import VideoDiscoveryError, VideoDiscoveryService


def test_video_discovery_requires_approved_source_with_video_feature(tmp_path) -> None:
    """Chỉ nguồn approved + feature video mới được discover video."""
    engine = create_engine(f"sqlite:///{tmp_path / 'video.db'}", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    from app.services.source_registry_service import SourceRegistryService

    registry = SourceRegistryService(session)

    # approved nhưng không bật video -> từ chối
    registry.upsert(
        domain="no-video.example",
        state=SourceStatus.APPROVED,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"video": False},
    )
    # approved và bật video -> cho phép
    registry.upsert(
        domain="video.example",
        state=SourceStatus.APPROVED,
        owner="team",
        distribution_evidence="evidence",
        feature_flags={"video": True},
    )
    session.commit()

    service = VideoDiscoveryService(registry)

    # Không bật video -> VideoDiscoveryError
    try:
        service.discover_videos("no-video.example", [{"url": "https://no-video.example/v1"}])
    except VideoDiscoveryError:
        pass
    else:
        raise AssertionError("phải nêu VideoDiscoveryError khi nguồn không bật video")

    # Bật video -> trả danh sách đã chuẩn hóa
    result = service.discover_videos(
        "video.example",
        [{"url": "https://video.example/v1", "title": "Video 1"}],
    )
    assert result == [
        {"url": "https://video.example/v1", "title": "Video 1", "source": "video.example"}
    ]

    # Nguồn unknown -> VideoDiscoveryError
    try:
        service.discover_videos("unknown.example", [{"url": "https://unknown.example/v1"}])
    except VideoDiscoveryError:
        pass
    else:
        raise AssertionError("phải nêu VideoDiscoveryError khi nguồn không đăng ký")
