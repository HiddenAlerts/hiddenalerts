"""Split run_logs skip telemetry into url / content / invalid counters

Additive and reversible. ``items_duplicate`` is retained and keeps being written
as the url + content total, so existing readers are unaffected; the new counters
carry the breakdown that makes a stalled source distinguishable from a correctly
deduplicating one.

Also adds the (source_id, run_started_at DESC) index the "latest runs for this
source" lookups need. The table already has idx_run_logs_source_id and
idx_run_logs_status; neither covers that ordering.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-28
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

_COUNTER_COLUMNS = (
    "items_skipped_url",
    "items_skipped_content",
    "items_skipped_invalid",
)

_INDEX_NAME = "idx_run_logs_source_started"


def upgrade() -> None:
    for column in _COUNTER_COLUMNS:
        op.add_column(
            "run_logs",
            sa.Column(
                column,
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )

    op.create_index(
        _INDEX_NAME,
        "run_logs",
        ["source_id", sa.text("run_started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="run_logs")

    for column in reversed(_COUNTER_COLUMNS):
        op.drop_column("run_logs", column)
