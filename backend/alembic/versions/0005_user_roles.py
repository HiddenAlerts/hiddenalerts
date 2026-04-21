"""Add role and profile fields to users table; seed optional test subscriber

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-22
"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column with server_default='admin' so all existing rows (the admin user)
    # get role='admin' automatically. We change the default to 'subscriber' after.
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="admin"),
    )
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "wants_high_alert_email",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "wants_digest_email",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "wants_weekly_report_email",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Switch the default to 'subscriber' for all future inserts.
    op.alter_column("users", "role", server_default="subscriber")

    # Optional test subscriber seed — safe to re-run (ON CONFLICT DO NOTHING)
    subscriber_email = os.environ.get("TEST_SUBSCRIBER_EMAIL", "")
    subscriber_password = os.environ.get("TEST_SUBSCRIBER_PASSWORD", "")
    subscriber_full_name = os.environ.get("TEST_SUBSCRIBER_FULL_NAME", "Test Subscriber")

    if subscriber_email and subscriber_password:
        try:
            from passlib.context import CryptContext

            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            hashed = pwd_context.hash(subscriber_password)

            conn = op.get_bind()
            conn.execute(
                sa.text(
                    "INSERT INTO users (email, password_hash, is_active, role, full_name) "
                    "VALUES (:email, :hash, true, 'subscriber', :full_name) "
                    "ON CONFLICT (email) DO NOTHING"
                ),
                {
                    "email": subscriber_email,
                    "hash": hashed,
                    "full_name": subscriber_full_name,
                },
            )
            print(f"Info: Test subscriber seeded — {subscriber_email}")
        except Exception as e:
            print(f"Warning: Could not seed test subscriber: {e}")
    else:
        print(
            "Info: TEST_SUBSCRIBER_EMAIL/TEST_SUBSCRIBER_PASSWORD not set — "
            "skipping subscriber seed."
        )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "wants_weekly_report_email")
    op.drop_column("users", "wants_digest_email")
    op.drop_column("users", "wants_high_alert_email")
    op.drop_column("users", "full_name")
    op.drop_column("users", "role")
