"""initial schema

Revision ID: 20260416_000001
Revises:
Create Date: 2026-04-16 00:00:01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260416_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telegram_users_telegram_user_id", "telegram_users", ["telegram_user_id"], unique=True)

    op.create_table(
        "chat_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_games_chat_id", "chat_games", ["chat_id"], unique=True)

    op.create_table(
        "game_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=255), nullable=False),
        sa.Column("buyin", sa.Numeric(12, 2), nullable=False),
        sa.Column("out", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["chat_games.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("game_id", "player_name", name="uq_game_player_name"),
    )
    op.create_index("ix_game_players_game_id", "game_players", ["game_id"], unique=False)

    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.telegram_user_id"]),
        sa.UniqueConstraint("stripe_subscription_id"),
    )
    op.create_index(
        "ix_user_subscriptions_telegram_user_id",
        "user_subscriptions",
        ["telegram_user_id"],
        unique=True,
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=255), nullable=False),
        sa.Column("processing_status", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stripe_events_event_id", "stripe_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_stripe_events_event_id", table_name="stripe_events")
    op.drop_table("stripe_events")

    op.drop_index("ix_user_subscriptions_telegram_user_id", table_name="user_subscriptions")
    op.drop_table("user_subscriptions")

    op.drop_index("ix_game_players_game_id", table_name="game_players")
    op.drop_table("game_players")

    op.drop_index("ix_chat_games_chat_id", table_name="chat_games")
    op.drop_table("chat_games")

    op.drop_index("ix_telegram_users_telegram_user_id", table_name="telegram_users")
    op.drop_table("telegram_users")
