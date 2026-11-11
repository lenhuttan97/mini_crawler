"""Add article metadata columns to documents (additive to 0002).

Nullable only, no backfill: existing documents keep their previous values
and new columns stay empty until a future crawl writes them.
Downgrade drops only these columns; metadata written while active is lost.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_document_article_metadata"
down_revision: str | None = "0002_worker_v1_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ARTICLE_COLUMNS = (
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("authors", sa.JSON(), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("section", sa.String(length=256), nullable=True),
    sa.Column("language", sa.String(length=35), nullable=True),
    sa.Column("article_html_key", sa.String(length=512), nullable=True),
)


def upgrade() -> None:
    for column in ARTICLE_COLUMNS:
        op.add_column("documents", column)


def downgrade() -> None:
    for column in reversed(ARTICLE_COLUMNS):
        op.drop_column("documents", column.name)
