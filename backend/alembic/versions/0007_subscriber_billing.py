"""Create subscriber_profiles, subscriptions, and stripe_webhook_events tables

Lays the database foundation for Authentication & Payment Phase 1:
  - subscriber_profiles mirrors Supabase Auth users and links them to a Stripe customer
  - subscriptions tracks the most recent Stripe subscription per subscriber profile
  - stripe_webhook_events stores Stripe event ids and payloads for idempotent webhook processing

No data is backfilled and no existing tables are altered. Existing admin auth (users table)
is untouched and remains the authoritative source for admin identities.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- SUBSCRIBER_PROFILES ---
    op.create_table(
        "subscriber_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("supabase_user_id", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default="subscriber",
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
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
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "supabase_user_id", name="uq_subscriber_profiles_supabase_user_id"
        ),
        sa.UniqueConstraint(
            "stripe_customer_id", name="uq_subscriber_profiles_stripe_customer_id"
        ),
    )
    op.create_index(
        "idx_subscriber_profiles_email", "subscriber_profiles", ["email"]
    )

    # --- SUBSCRIPTIONS ---
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "subscriber_profile_id",
            sa.Integer,
            sa.ForeignKey("subscriber_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("stripe_price_id", sa.String(64), nullable=True),
        sa.Column("plan_type", sa.String(16), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column(
            "current_period_start", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("canceled_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "stripe_subscription_id", name="uq_subscriptions_stripe_subscription_id"
        ),
    )
    op.create_index(
        "idx_subscriptions_subscriber_profile_id",
        "subscriptions",
        ["subscriber_profile_id"],
    )
    op.create_index(
        "idx_subscriptions_stripe_customer_id",
        "subscriptions",
        ["stripe_customer_id"],
    )
    op.create_index("idx_subscriptions_status", "subscriptions", ["status"])

    # --- STRIPE_WEBHOOK_EVENTS ---
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("stripe_event_id", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "stripe_event_id", name="uq_stripe_webhook_events_stripe_event_id"
        ),
    )
    op.create_index(
        "idx_stripe_webhook_events_event_type",
        "stripe_webhook_events",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_stripe_webhook_events_event_type", table_name="stripe_webhook_events"
    )
    op.drop_table("stripe_webhook_events")

    op.drop_index("idx_subscriptions_status", table_name="subscriptions")
    op.drop_index(
        "idx_subscriptions_stripe_customer_id", table_name="subscriptions"
    )
    op.drop_index(
        "idx_subscriptions_subscriber_profile_id", table_name="subscriptions"
    )
    op.drop_table("subscriptions")

    op.drop_index(
        "idx_subscriber_profiles_email", table_name="subscriber_profiles"
    )
    op.drop_table("subscriber_profiles")
