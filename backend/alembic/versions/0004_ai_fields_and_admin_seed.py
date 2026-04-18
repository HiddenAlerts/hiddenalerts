"""Add AI output fields to processed_alerts and seed admin user

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-06
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add AI raw output columns to processed_alerts
    op.add_column(
        "processed_alerts",
        sa.Column("financial_impact_estimate", sa.String(200), nullable=True),
    )
    op.add_column(
        "processed_alerts",
        sa.Column("victim_scale_raw", sa.String(50), nullable=True),
    )
    op.add_column(
        "processed_alerts",
        sa.Column("ai_model", sa.String(100), nullable=True),
    )

    # Seed admin user if env vars are provided
    # Uses ON CONFLICT DO NOTHING so re-running migration is safe (idempotent)
    admin_email = os.environ.get("ADMIN_EMAIL", "")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if admin_email and admin_password:
        try:
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed = pwd_context.hash(admin_password)

            conn = op.get_bind()
            conn.execute(
                sa.text(
                    "INSERT INTO users (email, password_hash, is_active) "
                    "VALUES (:email, :hash, true) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {"email": admin_email, "hash": hashed},
            )
        except Exception as e:
            # Log but don't fail migration if passlib unavailable during CI/test
            print(f"Warning: Could not seed admin user: {e}")
    else:
        print(
            "Info: ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping admin user seed. "
            "Set these env vars and re-run 'alembic upgrade head' to seed the admin user."
        )


def downgrade() -> None:
    op.drop_column("processed_alerts", "ai_model")
    op.drop_column("processed_alerts", "victim_scale_raw")
    op.drop_column("processed_alerts", "financial_impact_estimate")
    # Note: we do NOT delete the admin user on downgrade —
    # removing auth credentials automatically would be unsafe.
