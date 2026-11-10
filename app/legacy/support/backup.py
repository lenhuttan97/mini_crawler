"""Sao lưu/phục hồi cơ sở dữ liệu (P07-P08, §4 Operations and recovery).

Sử dụng dump SQL của engine hiện tại. Kiểm thử đơn vị chạy trên SQLite file
không cần PostgreSQL/MinIO thật; drill trên cơ sở hạ tầng thật được ghi nhận
là blocker do Docker daemon không khả dụng.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class BackupResult:
    """Kết quả sao lưu một cơ sở dữ liệu."""

    path: str
    size_bytes: int
    checksum_sha256: str
    created_at: str


class BackupService:
    """Sao lưu/phục hồi cơ sở dữ liệu qua tệp dump SQL."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def dump(self, output_path: str | Path) -> BackupResult:
        """Ghi dump SQL của cơ sở dữ liệu hiện tại vào tệp output_path."""
        output_path = Path(output_path)
        connection = self._engine.raw_connection()
        try:
            statements = "\n".join(connection.iterdump())
        finally:
            connection.close()
        output_path.write_text(statements, encoding="utf-8")
        data = output_path.read_bytes()
        return BackupResult(
            path=str(output_path),
            size_bytes=len(data),
            checksum_sha256=hashlib.sha256(data).hexdigest(),
            created_at=datetime.now(UTC).isoformat(),
        )

    def restore(self, input_path: str | Path) -> None:
        """Khôi phục cơ sở dữ liệu từ tệp dump SQL."""
        input_path = Path(input_path)
        if not input_path.is_file():
            raise FileNotFoundError(f"tệp sao lưu không tồn tại: {input_path}")
        script = input_path.read_text(encoding="utf-8")
        connection = self._engine.raw_connection()
        try:
            # Bỏ bảng hiện có để dump có thể tạo lại schema từ đầu.
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            for (table_name,) in tables:
                connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            connection.executescript(script)
            connection.commit()
        finally:
            connection.close()
