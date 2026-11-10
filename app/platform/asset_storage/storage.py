"""Storage adapter cho MinIO/S3 (P01 Item 6).

Object key do server tạo (UUID/hash), không được trích từ tiêu đề người dùng.
Mỗi hoạt động ghi nhận metadata; lỗi upload nêu StorageError để job service
không đánh completed.
"""

from __future__ import annotations

from dataclasses import dataclass

import boto3


@dataclass(frozen=True)
class StorageMetadata:
    """Metadata của object đã lưu trong object storage."""

    bucket: str
    key: str
    size: int
    content_type: str
    etag: str | None = None


class StorageError(Exception):
    """Lỗi khi tương tác object storage."""


class StorageAdapter:
    """Adapter đối với object storage (MinIO/S3-compatible) qua boto3."""

    def __init__(self, s3_client=None, endpoint_url: str | None = None) -> None:
        if s3_client is not None:
            self._s3 = s3_client
        elif endpoint_url:
            self._s3 = boto3.client("s3", endpoint_url=endpoint_url)
        else:
            self._s3 = boto3.client("s3")

    def upload_object(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StorageMetadata:
        """Tải object lên storage. Trả metadata; lỗi nêu StorageError."""
        try:
            response = self._s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
        except Exception as exc:
            raise StorageError(f"upload object {bucket}/{key} thất bại: {exc}") from exc
        return StorageMetadata(
            bucket=bucket,
            key=key,
            size=len(data),
            content_type=content_type,
            etag=response.get("ETag", "").strip('"') if response.get("ETag") else None,
        )

    def download_object(self, *, bucket: str, key: str) -> bytes:
        """Tải object về dưới dạng bytes."""
        try:
            response = self._s3.get_object(Bucket=bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"download object {bucket}/{key} thất bại: {exc}") from exc
        body = response["Body"]
        return body.read() if hasattr(body, "read") else body

    def delete_object(self, *, bucket: str, key: str) -> None:
        """Xóa object khỏi storage."""
        try:
            self._s3.delete_object(Bucket=bucket, Key=key)
        except Exception as exc:
            raise StorageError(f"delete object {bucket}/{key} thất bại: {exc}") from exc

    def generate_presigned_url(self, *, bucket: str, key: str, ttl_seconds: int) -> str:
        """Tạo URL truy cập tạm thời (private, không public object)."""
        try:
            return self._s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except Exception as exc:
            raise StorageError(f"generate presigned url {bucket}/{key} thất bại: {exc}") from exc
