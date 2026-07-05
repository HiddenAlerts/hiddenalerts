"""Widen all Stripe-id VARCHAR(64) columns to VARCHAR(255)

Hotfix for a production crash in ``POST /api/v1/billing/checkout``: Stripe
returned a checkout session id of 66 chars (``cs_test_…``) and the UPDATE
into ``billing_checkout_attempts.stripe_checkout_session_id`` (VARCHAR(64))
failed with ``StringDataRightTruncationError`` at commit time → 500.

Stripe documents object IDs up to 255 chars and recent IDs already routinely
exceed 64. Widening every ``stripe_*_id`` / ``stripe_price_id`` column across
the four billing-related tables removes this whole class of latent failure
(it would have bitten the webhook upsert path next).

This migration is a pure ``ALTER COLUMN ... TYPE VARCHAR(255)`` — Postgres
performs it in-place, no table rewrite, no data loss. Existing data fits
trivially. Downgrade narrows back to VARCHAR(64); if any current value is
longer the downgrade will fail (intentional — never silently truncate live
data).

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


# (table, column) pairs that were previously VARCHAR(64).
_COLUMNS = (
    ("subscriber_profiles", "stripe_customer_id"),
    ("subscriptions", "stripe_customer_id"),
    ("subscriptions", "stripe_subscription_id"),
    ("subscriptions", "stripe_price_id"),
    ("stripe_webhook_events", "stripe_event_id"),
    ("billing_checkout_attempts", "stripe_checkout_session_id"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(64),
            type_=sa.String(255),
            existing_nullable=True,
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.String(255),
            type_=sa.String(64),
            existing_nullable=True,
        )
