"""Add V1 Alert Publishing state + review-audit fields (additive, reversible)

V1 Alert Publishing Slice 1 — schema/model foundation only. This migration adds
publication-state columns to ``processed_alerts`` and two audit columns to
``alert_reviews``. It is purely additive:

  * Every new nullable column defaults to NULL on existing rows.
  * Every new boolean column is NOT NULL with ``server_default = false`` so
    existing rows are backfilled to ``false`` by Postgres without a data step.

No existing column is altered, no row is rewritten beyond the boolean
server-default backfill, and no runtime publishing/scoring/grouping behaviour
changes. The columns are written by no code path yet — wiring happens in later
V1 slices. Downgrade drops exactly what upgrade added.

Controlled vocabulary for the text columns lives in
``app.pipeline.publishing.constants`` (risk_band, publish_decision,
pending_review_reason, publication_state_source, decision_source).

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


# New columns on processed_alerts: (name, type, nullable, server_default)
_PROCESSED_ALERT_COLUMNS = (
    ("risk_band", sa.String(20), True, None),
    ("publish_decision", sa.String(20), True, None),
    ("publish_decision_reason", sa.Text(), True, None),
    ("pending_review_reason", sa.String(50), True, None),
    ("is_excluded", sa.Boolean(), False, sa.false()),
    ("excluded_reason", sa.Text(), True, None),
    ("is_manual_hold", sa.Boolean(), False, sa.false()),
    ("published_by_rule", sa.Boolean(), False, sa.false()),
    ("publishing_policy_version", sa.String(50), True, None),
    ("publication_state_source", sa.String(50), True, None),
    ("publication_state_updated_at", sa.TIMESTAMP(timezone=True), True, None),
)

# New indexes on processed_alerts: (index_name, column)
_PROCESSED_ALERT_INDEXES = (
    ("idx_processed_alerts_risk_band", "risk_band"),
    ("idx_processed_alerts_pending_review_reason", "pending_review_reason"),
    ("idx_processed_alerts_publish_decision", "publish_decision"),
    ("idx_processed_alerts_publication_state_source", "publication_state_source"),
)

# New columns on alert_reviews: (name, type, nullable, server_default)
_ALERT_REVIEW_COLUMNS = (
    ("review_batch_id", sa.String(100), True, None),
    ("decision_source", sa.String(50), True, None),
)


def upgrade() -> None:
    for name, type_, nullable, server_default in _PROCESSED_ALERT_COLUMNS:
        op.add_column(
            "processed_alerts",
            sa.Column(name, type_, nullable=nullable, server_default=server_default),
        )

    for index_name, column in _PROCESSED_ALERT_INDEXES:
        op.create_index(index_name, "processed_alerts", [column])

    for name, type_, nullable, server_default in _ALERT_REVIEW_COLUMNS:
        op.add_column(
            "alert_reviews",
            sa.Column(name, type_, nullable=nullable, server_default=server_default),
        )


def downgrade() -> None:
    for name, _type, _nullable, _default in reversed(_ALERT_REVIEW_COLUMNS):
        op.drop_column("alert_reviews", name)

    for index_name, _column in reversed(_PROCESSED_ALERT_INDEXES):
        op.drop_index(index_name, table_name="processed_alerts")

    for name, _type, _nullable, _default in reversed(_PROCESSED_ALERT_COLUMNS):
        op.drop_column("processed_alerts", name)
