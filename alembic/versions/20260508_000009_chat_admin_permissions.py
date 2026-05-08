"""chat admin permissions

Revision ID: 20260508_000009
Revises: 20260425_000008
Create Date: 2026-05-08 00:00:09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_000009"
down_revision = "20260425_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_admin_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("telegram_user_id", "chat_id", name="uq_chat_admin_permission_user_chat"),
    )
    op.create_index(
        "ix_chat_admin_permissions_telegram_user_id",
        "chat_admin_permissions",
        ["telegram_user_id"],
        unique=False,
    )
    op.create_index("ix_chat_admin_permissions_chat_id", "chat_admin_permissions", ["chat_id"], unique=False)
    op.create_index("ix_chat_admin_permissions_is_active", "chat_admin_permissions", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_admin_permissions_is_active", table_name="chat_admin_permissions")
    op.drop_index("ix_chat_admin_permissions_chat_id", table_name="chat_admin_permissions")
    op.drop_index("ix_chat_admin_permissions_telegram_user_id", table_name="chat_admin_permissions")
    op.drop_table("chat_admin_permissions")
