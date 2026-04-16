"""subscription acl fields

Revision ID: 20260417_000003
Revises: 20260416_000002
Create Date: 2026-04-17 00:00:03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_000003"
down_revision = "20260416_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_subscriptions", sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column("user_subscriptions", sa.Column("provider_status", sa.String(length=64), nullable=True))
    op.add_column("user_subscriptions", sa.Column("requested_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("user_subscriptions", sa.Column("pending_since", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_subscriptions", sa.Column("last_pending_reminder_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_subscriptions", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_subscriptions",
        sa.Column("cancel_requested_by_telegram_user_id", sa.BigInteger(), nullable=True),
    )

    op.execute("UPDATE user_subscriptions SET provider = 'stripe' WHERE provider IS NULL")
    op.execute("UPDATE user_subscriptions SET provider_status = status WHERE provider_status IS NULL")
    op.alter_column("user_subscriptions", "provider", nullable=False)


def downgrade() -> None:
    op.drop_column("user_subscriptions", "cancel_requested_by_telegram_user_id")
    op.drop_column("user_subscriptions", "cancel_requested_at")
    op.drop_column("user_subscriptions", "last_pending_reminder_at")
    op.drop_column("user_subscriptions", "pending_since")
    op.drop_column("user_subscriptions", "requested_chat_id")
    op.drop_column("user_subscriptions", "provider_status")
    op.drop_column("user_subscriptions", "provider")
