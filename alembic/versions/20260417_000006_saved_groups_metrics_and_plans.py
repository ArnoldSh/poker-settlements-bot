"""saved groups, product metrics, and subscription plan codes

Revision ID: 20260417_000006
Revises: 20260417_000005
Create Date: 2026-04-17 00:00:06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_000006"
down_revision = "20260417_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_subscriptions", sa.Column("plan_code", sa.String(length=64), nullable=True))

    op.create_table(
        "saved_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_telegram_user_id", "name", name="uq_saved_group_owner_name"),
    )
    op.create_index("ix_saved_groups_owner_telegram_user_id", "saved_groups", ["owner_telegram_user_id"], unique=False)
    op.create_index("ix_saved_groups_name", "saved_groups", ["name"], unique=False)

    op.create_table(
        "saved_group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["saved_groups.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("group_id", "player_name", name="uq_saved_group_member_name"),
    )
    op.create_index("ix_saved_group_members_group_id", "saved_group_members", ["group_id"], unique=False)

    op.create_table(
        "product_metric_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("properties_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["chat_games.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_product_metric_events_event_name", "product_metric_events", ["event_name"], unique=False)
    op.create_index("ix_product_metric_events_telegram_user_id", "product_metric_events", ["telegram_user_id"], unique=False)
    op.create_index("ix_product_metric_events_chat_id", "product_metric_events", ["chat_id"], unique=False)
    op.create_index("ix_product_metric_events_created_at", "product_metric_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_metric_events_created_at", table_name="product_metric_events")
    op.drop_index("ix_product_metric_events_chat_id", table_name="product_metric_events")
    op.drop_index("ix_product_metric_events_telegram_user_id", table_name="product_metric_events")
    op.drop_index("ix_product_metric_events_event_name", table_name="product_metric_events")
    op.drop_table("product_metric_events")

    op.drop_index("ix_saved_group_members_group_id", table_name="saved_group_members")
    op.drop_table("saved_group_members")

    op.drop_index("ix_saved_groups_name", table_name="saved_groups")
    op.drop_index("ix_saved_groups_owner_telegram_user_id", table_name="saved_groups")
    op.drop_table("saved_groups")

    op.drop_column("user_subscriptions", "plan_code")
