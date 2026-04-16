"""game status and subscription period window

Revision ID: 20260416_000002
Revises: 20260416_000001
Create Date: 2026-04-16 00:00:02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_000002"
down_revision = "20260416_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_chat_games_chat_id", table_name="chat_games")
    op.add_column("chat_games", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("chat_games", sa.Column("finalized_by_telegram_user_id", sa.BigInteger(), nullable=True))
    op.add_column("chat_games", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE chat_games SET status = 'open' WHERE status IS NULL")
    op.alter_column("chat_games", "status", nullable=False)
    op.create_index("ix_chat_games_chat_id", "chat_games", ["chat_id"], unique=False)
    op.create_index("ix_chat_games_status", "chat_games", ["status"], unique=False)

    op.add_column("user_subscriptions", sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_subscriptions", "current_period_start")

    op.drop_index("ix_chat_games_status", table_name="chat_games")
    op.drop_index("ix_chat_games_chat_id", table_name="chat_games")
    op.drop_column("chat_games", "finalized_at")
    op.drop_column("chat_games", "finalized_by_telegram_user_id")
    op.drop_column("chat_games", "status")
    op.create_index("ix_chat_games_chat_id", "chat_games", ["chat_id"], unique=True)
