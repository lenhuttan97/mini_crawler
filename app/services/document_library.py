"""S04 Document library (P06).

List/filter/paginate document đã chuẩn hóa. Không gọi mạng thật.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.domain.models import Document


@dataclass(frozen=True)
class DocumentPage:
    """Trang kết quả danh sách document."""

    items: list[Document]
    page: int
    page_size: int
    total: int
    total_pages: int


class DocumentLibrary:
    """Truy vấn thư viện document đã crawl."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_documents(
        self,
        *,
        caller_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
        document_type: str | None = None,
    ) -> DocumentPage:
        """Lấy trang document (phân trang, tùy chọn lọc theo loại)."""
        query = self._session.query(Document)
        if document_type is not None:
            query = query.filter_by(document_type=document_type)
        total = query.count()
        items = (
            query.order_by(Document.crawled_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return DocumentPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size > 0 else 0,
        )
