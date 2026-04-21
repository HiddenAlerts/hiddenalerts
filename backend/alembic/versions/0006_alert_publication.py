"""Add publication state fields to processed_alerts

Adds is_published, published_at, published_by_user_id to support the
Tier 1/2/3 alert publication workflow introduced in M3 Slice 2.

Existing rows default to is_published = false. Historical alerts remain
unpublished after migration and must be explicitly published by an admin
or by the pipeline re-processing future items.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processed_alerts",
        sa.Column(
            "is_published",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "processed_alerts",
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "processed_alerts",
        sa.Column(
            "published_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Partial index — only indexes published rows, so it stays small and fast
    # for subscriber feed queries that always filter WHERE is_published = true.
    op.create_index(
        "idx_processed_alerts_published",
        "processed_alerts",
        ["is_published"],
        postgresql_where=sa.text("is_published = true"),
    )


def downgrade() -> None:
    op.drop_index("idx_processed_alerts_published", table_name="processed_alerts")
    op.drop_column("processed_alerts", "published_by_user_id")
    op.drop_column("processed_alerts", "published_at")
    op.drop_column("processed_alerts", "is_published")
