"""Tests cho media service (P03 Item 1).

Tạo media job, validate manifest, quota item/tổng byte, dedupe theo checksum.
Storage/downloader bị mock, không gọi mạng thật.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.network_policy.policy import PolicyDecision
from app.platform.persistence.models import Base, MediaJob, MediaJobItem
from app.services.media import MediaManifestError, MediaQuotaExceeded, MediaService


@pytest.fixture
def db_session(tmp_path):
    db_path = str(tmp_path / "media.db")
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()


def _allow_policy():
    return type(
        "AllowPolicy",
        (),
        {"evaluate": lambda self, _command: PolicyDecision(True, None, None)},
    )()


def test_create_media_job_single(db_session) -> None:
    """Tạo media job đơn lẻ với item, status pending."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    job = service.create_media_job(
        caller_id="user-1",
        input_type="direct",
        source_url="https://example.com/image.png",
        idempotency_key="media-idem-1",
    )
    assert job.id is not None
    assert job.input_type == "direct"
    assert job.status == "pending"
    assert db_session.query(MediaJobItem).count() == 1


def test_create_media_job_batch(db_session) -> None:
    """Tạo media job batch nhiều items, mỗi item có sequence."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    job = service.create_media_job(
        caller_id="user-1",
        input_type="image_batch",
        source_url="https://example.com/manifest",
        idempotency_key="media-idem-2",
        items=[
            {"source_url": "https://example.com/a.png", "sequence": 1},
            {"source_url": "https://example.com/b.png", "sequence": 2},
        ],
    )
    items = (
        db_session.query(MediaJobItem)
        .filter_by(media_job_id=job.id)
        .order_by(MediaJobItem.sequence)
        .all()
    )
    assert len(items) == 2
    assert items[0].sequence == 1
    assert items[1].sequence == 2


def test_idempotency_media_job(db_session) -> None:
    """Cùng caller_id + idempotency_key => trả lại job cũ, không tạo trùng."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    job1 = service.create_media_job(
        caller_id="user-1",
        input_type="direct",
        source_url="https://example.com/a.png",
        idempotency_key="media-idem-3",
    )
    job2 = service.create_media_job(
        caller_id="user-1",
        input_type="direct",
        source_url="https://example.com/a.png",
        idempotency_key="media-idem-3",
    )
    assert job1.id == job2.id
    assert db_session.query(MediaJob).count() == 1


def test_media_idempotency_is_scoped_to_caller(db_session) -> None:
    """Different callers may reuse a key without observing each other's media job."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    first = service.create_media_job(
        caller_id="user-1",
        input_type="direct",
        source_url="https://example.com/a.png",
        idempotency_key="shared-key",
    )
    second = service.create_media_job(
        caller_id="user-2",
        input_type="direct",
        source_url="https://example.com/b.png",
        idempotency_key="shared-key",
    )

    assert first.id != second.id
    assert db_session.query(MediaJob).count() == 2


def test_quota_max_items(db_session) -> None:
    """Vượt max item count => MediaQuotaExceeded."""
    service = MediaService(session=db_session, max_items=2, policy_gate=_allow_policy())
    with pytest.raises(MediaQuotaExceeded):
        service.create_media_job(
            caller_id="user-1",
            input_type="image_batch",
            source_url="https://example.com/m",
            idempotency_key="media-idem-4",
            items=[
                {"source_url": "https://example.com/a.png", "sequence": 1},
                {"source_url": "https://example.com/b.png", "sequence": 2},
                {"source_url": "https://example.com/c.png", "sequence": 3},
            ],
        )


def test_manifest_error_no_items(db_session) -> None:
    """Batch image không được để trống danh sách items."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    with pytest.raises(MediaManifestError, match="item"):
        service.create_media_job(
            caller_id="user-1",
            input_type="image_batch",
            source_url="https://example.com/m",
            idempotency_key="media-idem-5",
            items=[],
        )


def test_duplicate_request_url_in_batch(db_session) -> None:
    """Trùng source_url trong cùng batch => MediaManifestError."""
    service = MediaService(session=db_session, policy_gate=_allow_policy())
    with pytest.raises(MediaManifestError, match="trùng|duplicate"):
        service.create_media_job(
            caller_id="user-1",
            input_type="image_batch",
            source_url="https://example.com/m",
            idempotency_key="media-idem-6",
            items=[
                {"source_url": "https://example.com/a.png", "sequence": 1},
                {"source_url": "https://example.com/a.png", "sequence": 2},
            ],
        )


def test_policy_denied_item_creates_no_media_job(db_session) -> None:
    """A denied direct-media URL stops before media job/item persistence."""
    from app.services.media import MediaPolicyBlocked

    policy_gate = type(
        "DenyPolicy",
        (),
        {
            "evaluate": lambda self, _command: PolicyDecision(
                False,
                "ssrf_private_ip",
                "private destination",
            )
        },
    )()
    service = MediaService(session=db_session, policy_gate=policy_gate)

    with pytest.raises(MediaPolicyBlocked, match="ssrf_private_ip"):
        service.create_media_job(
            caller_id="user-1",
            input_type="direct",
            source_url="http://127.0.0.1/image.png",
            idempotency_key="media-blocked-1",
        )

    assert db_session.query(MediaJob).count() == 0
    assert db_session.query(MediaJobItem).count() == 0
