"""Create intelligence_briefs table (Intelligence Brief Module Phase 1)

Greenfield, additive migration. Creates the ``intelligence_briefs`` table with
its unique constraints (``slug``, ``brief_code``), btree indexes on the columns
subscriber/admin queries filter on, and GIN indexes on the two JSONB columns
used for containment filters (``tags``, ``primary_entities``).

Controlled vocabulary for the enum-like text columns lives in
``app.models.intelligence_brief_constants``.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


# Btree indexes: (index_name, column). GIN indexes are created separately since
# they need the postgresql_using kwarg.
_BTREE_INDEXES = (
    ("idx_intelligence_briefs_status", "status"),
    ("idx_intelligence_briefs_risk_level", "risk_level"),
    ("idx_intelligence_briefs_category", "category"),
    ("idx_intelligence_briefs_is_featured", "is_featured"),
    ("idx_intelligence_briefs_brief_type", "brief_type"),
    ("idx_intelligence_briefs_is_premium", "is_premium"),
    ("idx_intelligence_briefs_published_at", "published_at"),
)

_GIN_INDEXES = (
    ("idx_intelligence_briefs_tags_gin", "tags"),
    ("idx_intelligence_briefs_primary_entities_gin", "primary_entities"),
)


def upgrade() -> None:
    op.create_table(
        "intelligence_briefs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brief_code", sa.String(length=32), nullable=False),
        # Basic information
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=True),
        sa.Column("primary_entities", postgresql.JSONB(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("featured_image_url", sa.String(length=1000), nullable=True),
        sa.Column("featured_image_path", sa.String(length=1000), nullable=True),
        sa.Column("time_horizon", sa.String(length=30), nullable=True),
        # Intelligence content
        sa.Column("executive_summary", sa.Text(), nullable=True),
        sa.Column("why_this_matters", sa.Text(), nullable=True),
        sa.Column("key_signals", postgresql.JSONB(), nullable=True),
        sa.Column("risk_assessment", sa.Text(), nullable=True),
        sa.Column("what_others_miss", sa.Text(), nullable=True),
        sa.Column("implications", sa.Text(), nullable=True),
        sa.Column("main_intelligence_brief", sa.Text(), nullable=True),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.Column("supporting_alerts", postgresql.JSONB(), nullable=True),
        sa.Column(
            "alerts_count", sa.Integer(), nullable=False, server_default="0"
        ),
        # Publishing / lifecycle
        sa.Column("confidence_level", sa.String(length=20), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="draft"
        ),
        sa.Column(
            "is_featured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "published_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Future-ready fields
        sa.Column(
            "brief_type",
            sa.String(length=50),
            nullable=False,
            server_default="intelligence_brief",
        ),
        sa.Column("featured_order", sa.Integer(), nullable=True),
        sa.Column(
            "read_time_minutes",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "is_premium",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.UniqueConstraint("slug", name="uq_intelligence_briefs_slug"),
        sa.UniqueConstraint("brief_code", name="uq_intelligence_briefs_brief_code"),
    )

    for index_name, column in _BTREE_INDEXES:
        op.create_index(index_name, "intelligence_briefs", [column])

    for index_name, column in _GIN_INDEXES:
        op.create_index(
            index_name,
            "intelligence_briefs",
            [column],
            postgresql_using="gin",
        )


def downgrade() -> None:
    for index_name, _column in reversed(_GIN_INDEXES):
        op.drop_index(index_name, table_name="intelligence_briefs")

    for index_name, _column in reversed(_BTREE_INDEXES):
        op.drop_index(index_name, table_name="intelligence_briefs")

    op.drop_table("intelligence_briefs")
