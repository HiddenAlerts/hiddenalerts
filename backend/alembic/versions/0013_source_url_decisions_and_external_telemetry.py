"""Durable source-specific URL decisions, plus run_logs external telemetry

An excluded URL creates no ``raw_items`` row, so it stays "unseen" and is
requested again on every scheduled run — the 2026-07-31 preview measured 45 such
URLs in a 50-item FBI sample. ``source_url_decisions`` records the verdict
instead, keyed by (source, URL) so the same article can be excluded under one
source and collected under another.

``run_logs.items_skipped_external`` separates those deliberate exclusions from
``items_skipped_invalid``, which until now absorbed them. Existing rows become 0,
which is accurate: no run before this migration recorded an exclusion.

Additive and reversible. Nothing is backfilled and no historical row changes.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-31
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

_TABLE = "source_url_decisions"
_RUN_LOG_COLUMN = "items_skipped_external"
_UNIQUE_CONSTRAINT = "uq_source_url_decisions_source_url"
_INDEXES = (
    ("idx_source_url_decisions_source_id", ["source_id"]),
    ("idx_source_url_decisions_decision", ["decision"]),
    ("idx_source_url_decisions_source_decision", ["source_id", "decision"]),
)


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("item_url", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=False),
        sa.Column("destination_host", sa.String(length=255), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column(
            "first_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "occurrence_count", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.UniqueConstraint("source_id", "url_hash", name=_UNIQUE_CONSTRAINT),
    )

    for name, columns in _INDEXES:
        op.create_index(name, _TABLE, columns)

    # NOT NULL with a zero default, so every existing run reads as "no exclusions"
    # rather than as unknown.
    op.add_column(
        "run_logs",
        sa.Column(
            _RUN_LOG_COLUMN,
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("run_logs", _RUN_LOG_COLUMN)

    for name, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=_TABLE)

    # The unique constraint and the foreign key go with the table.
    op.drop_table(_TABLE)
