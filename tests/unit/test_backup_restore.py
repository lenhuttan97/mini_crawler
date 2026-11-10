"""Backup/restore drill tests (P07-P08, §4 Operations and recovery).

Dùng SQLite file để kiểm thử logic sao lưu/phục hồi mà không cần PostgreSQL
hay MinIO thật. Docker integration drill được ghi nhận là blocker riêng.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.platform.persistence.models import Base, Job
from app.services.backup import BackupResult, BackupService


def _make_engine(tmp_path, name: str):
    engine = create_engine(f"sqlite:///{tmp_path / name}", future=True)
    Base.metadata.create_all(engine)
    return engine


def test_backup_dump_creates_file_with_metadata(tmp_path) -> None:
    """dump() tạo tệp SQL, trả metadata (kích thước, checksum SHA-256, thời gian)."""
    engine = _make_engine(tmp_path, "source.db")
    session = sessionmaker(bind=engine, future=True)()
    session.add(
        Job(id="job-1", type="crawl", status="pending", caller_id="user-1", idempotency_key="k-1")
    )
    session.commit()
    session.close()

    service = BackupService(engine)
    dump_path = tmp_path / "backup.sql"
    result = service.dump(dump_path)

    assert isinstance(result, BackupResult)
    assert dump_path.is_file()
    assert result.path == str(dump_path)
    assert result.size_bytes > 0
    assert result.checksum_sha256 == hashlib.sha256(dump_path.read_bytes()).hexdigest()
    assert result.created_at is not None
    assert "job-1" in dump_path.read_text(encoding="utf-8")


def test_backup_restore_round_trip_preserves_data(tmp_path) -> None:
    """Dữ liệu được lưu vào bản sao và khôi phục được vào cơ sở dữ liệu mới."""
    source = _make_engine(tmp_path, "source.db")
    session = sessionmaker(bind=source, future=True)()
    session.add(
        Job(id="job-1", type="crawl", status="pending", caller_id="user-1", idempotency_key="k-1")
    )
    session.commit()
    session.close()

    dump_path = tmp_path / "backup.sql"
    BackupService(source).dump(dump_path)

    target = _make_engine(tmp_path, "target.db")
    BackupService(target).restore(dump_path)

    session2 = sessionmaker(bind=target, future=True)()
    restored = session2.get(Job, "job-1")
    session2.close()

    assert restored is not None
    assert restored.id == "job-1"
    assert restored.type == "crawl"
    assert restored.caller_id == "user-1"


def test_backup_restore_missing_file_raises(tmp_path) -> None:
    """restore() từ tệp không tồn tại phải nêu lỗi rõ ràng."""
    engine = _make_engine(tmp_path, "target.db")
    service = BackupService(engine)

    missing = tmp_path / "does-not-exist.sql"
    try:
        service.restore(missing)
    except FileNotFoundError:
        return
    raise AssertionError("restore() phải nêu FileNotFoundError khi tệp sao lưu không tồn tại")
