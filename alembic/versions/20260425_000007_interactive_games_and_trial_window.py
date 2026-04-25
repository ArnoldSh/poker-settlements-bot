"""interactive games and trial window support

Revision ID: 20260425_000007
Revises: 20260417_000006
Create Date: 2026-04-25 00:00:07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260425_000007"
down_revision = "20260417_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_games", sa.Column("input_mode", sa.String(length=32), nullable=False, server_default="manual"))
    op.add_column("chat_games", sa.Column("interactive_phase", sa.String(length=32), nullable=True))
    op.create_index("ix_chat_games_input_mode", "chat_games", ["input_mode"], unique=False)

    op.create_table(
        "interactive_game_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("player_name", sa.String(length=255), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("raw_text", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["chat_games.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("game_id", "telegram_message_id", name="uq_interactive_game_message"),
    )
    op.create_index("ix_interactive_game_messages_game_id", "interactive_game_messages", ["game_id"], unique=False)
    op.create_index("ix_interactive_game_messages_chat_id", "interactive_game_messages", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_interactive_game_messages_chat_id", table_name="interactive_game_messages")
    op.drop_index("ix_interactive_game_messages_game_id", table_name="interactive_game_messages")
    op.drop_table("interactive_game_messages")
    op.drop_index("ix_chat_games_input_mode", table_name="chat_games")
    op.drop_column("chat_games", "interactive_phase")
    op.drop_column("chat_games", "input_mode")
