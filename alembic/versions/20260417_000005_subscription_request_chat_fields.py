"""subscription request chat fields

Revision ID: 20260417_000005
Revises: 20260417_000004
Create Date: 2026-04-17 00:00:05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_000005"
down_revision = "20260417_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_subscriptions", sa.Column("cancel_requested_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("user_subscriptions", sa.Column("refund_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "user_subscriptions",
        sa.Column("refund_requested_by_telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column("user_subscriptions", sa.Column("refund_requested_chat_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_subscriptions", "refund_requested_chat_id")
    op.drop_column("user_subscriptions", "refund_requested_by_telegram_user_id")
    op.drop_column("user_subscriptions", "refund_requested_at")
    op.drop_column("user_subscriptions", "cancel_requested_chat_id")
