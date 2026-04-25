"""manual buyin entries

Revision ID: 20260425_000008
Revises: 20260425_000007
Create Date: 2026-04-25 00:00:08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260425_000008"
down_revision = "20260425_000007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_buyin_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_text", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["chat_games.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_game_buyin_entries_game_id", "game_buyin_entries", ["game_id"], unique=False)
    op.create_index("ix_game_buyin_entries_player_name", "game_buyin_entries", ["player_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_game_buyin_entries_player_name", table_name="game_buyin_entries")
    op.drop_index("ix_game_buyin_entries_game_id", table_name="game_buyin_entries")
    op.drop_table("game_buyin_entries")
