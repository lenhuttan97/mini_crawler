"""Local filesystem object storage for developer runtime modes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.platform.asset_storage.storage import StorageError, StorageMetadata


class LocalStorageAdapter:
    """Store objects below a configured root using server-generated keys."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root).expanduser().resolve()

    def upload_object(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StorageMetadata:
        """Atomically write bytes below the root and return safe metadata."""
        target = self._resolve(bucket, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd, temp_name = tempfile.mkstemp(dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                os.replace(temp_name, target)
            except BaseException:
                Path(temp_name).unlink(missing_ok=True)
                raise
        except OSError as exc:
            raise StorageError(f"upload object {bucket}/{key} thất bại: {exc}") from exc
        return StorageMetadata(
            bucket=bucket,
            key=key,
            size=len(data),
            content_type=content_type,
        )

    def download_object(self, *, bucket: str, key: str) -> bytes:
        """Read an object; IO failures are typed storage errors."""
        target = self._resolve(bucket, key)
        try:
            return target.read_bytes()
        except OSError as exc:
            raise StorageError(f"download object {bucket}/{key} thất bại: {exc}") from exc

    def delete_object(self, *, bucket: str, key: str) -> None:
        """Delete an object; deleting an absent object succeeds."""
        target = self._resolve(bucket, key)
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError(f"delete object {bucket}/{key} thất bại: {exc}") from exc

    def _resolve(self, bucket: str, key: str) -> Path:
        if not bucket or Path(bucket).name != bucket:
            raise StorageError("bucket không hợp lệ")
        if not key or Path(key).is_absolute() or ".." in Path(key).parts:
            raise StorageError("object key không hợp lệ")
        candidate = (self._root / bucket / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise StorageError("object key vượt ra ngoài storage root")
        return candidate
