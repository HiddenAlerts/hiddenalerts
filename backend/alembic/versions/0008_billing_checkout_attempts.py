"""Add billing_checkout_attempts table for checkout request idempotency

Powers Auth/Payment Phase 1 Slice 6's protection against duplicate Stripe
Checkout Sessions from network retries, double-clicks, and frontend retries
without an idempotency key. One unique ``idempotency_key`` per attempt;
``status`` tracks ``pending`` → ``succeeded`` / ``failed`` so a retry can
either reuse the prior ``checkout_url`` or try again cleanly.

Additive migration — no existing tables touched.

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_checkout_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "subscriber_profile_id",
            sa.Integer,
            sa.ForeignKey("subscriber_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_type", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(64), nullable=True),
        sa.Column("checkout_url", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
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
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_billing_checkout_attempts_idempotency_key",
        ),
    )
    op.create_index(
        "idx_billing_checkout_attempts_subscriber_profile_id",
        "billing_checkout_attempts",
        ["subscriber_profile_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_billing_checkout_attempts_subscriber_profile_id",
        table_name="billing_checkout_attempts",
    )
    op.drop_table("billing_checkout_attempts")
