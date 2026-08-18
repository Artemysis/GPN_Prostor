"""add requests.deleted_at (soft-delete) + миграция статусов in_progress/ready -> draft

Revision ID: 0002_request_deleted_at
Revises: 0001_initial
Create Date: 2026-08-18

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_request_deleted_at"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE requests SET status = 'draft' WHERE status IN ('in_progress', 'ready')")


def downgrade() -> None:
    op.drop_column("requests", "deleted_at")
