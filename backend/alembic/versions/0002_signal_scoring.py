"""Add signal scoring fields to sources and processed_alerts

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-23
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Credibility scores per source (name → score)
_CREDIBILITY_SCORES = {
    "SEC Press Releases": 5,
    "FTC RSS Feeds": 4,
    "FinCEN Press Releases": 4,
    "IC3 Press Releases": 4,
    "FBI National Press Releases": 5,
    "FBI News Blog RSS": 5,
    "FBI in the News RSS": 5,
    "DOJ Press Releases": 5,
    "KrebsOnSecurity": 3,
    "BleepingComputer": 3,
}


def upgrade() -> None:
    # --- sources: add credibility_score ---
    op.add_column(
        "sources",
        sa.Column("credibility_score", sa.Integer, nullable=False, server_default="3"),
    )

    # Update each source's credibility score
    conn = op.get_bind()
    for name, score in _CREDIBILITY_SCORES.items():
        conn.execute(
            sa.text("UPDATE sources SET credibility_score = :score WHERE name = :name"),
            {"score": score, "name": name},
        )

    # --- processed_alerts: add signal scoring columns ---
    for col in (
        "score_source_credibility",
        "score_financial_impact",
        "score_victim_scale",
        "score_cross_source",
        "score_trend_acceleration",
        "signal_score_total",
    ):
        op.add_column(
            "processed_alerts",
            sa.Column(col, sa.Integer, nullable=True),
        )

    op.create_index("idx_processed_alerts_score", "processed_alerts", ["signal_score_total"])


def downgrade() -> None:
    op.drop_index("idx_processed_alerts_score", table_name="processed_alerts")

    for col in (
        "signal_score_total",
        "score_trend_acceleration",
        "score_cross_source",
        "score_victim_scale",
        "score_financial_impact",
        "score_source_credibility",
    ):
        op.drop_column("processed_alerts", col)

    op.drop_column("sources", "credibility_score")
