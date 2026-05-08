"""subscription plans

Revision ID: 20260508_000010
Revises: 20260508_000009
Create Date: 2026-05-08 00:00:10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_000010"
down_revision = "20260508_000009"
branch_labels = None
depends_on = None


PLAN_ROWS = (
    ("monthly", "1m", "Monthly", "monthly", "price_1TOk3X1FJ9pFBGpFYWPsPZ6c", 499, "eur"),
    ("quarterly", "3m", "Quarterly", "quarterly", "price_1TUvW91FJ9pFBGpFQZfLLvFp", 999, "eur"),
    ("semiannual", "6m", "Semiannual", "semiannual", "price_1TUvXk1FJ9pFBGpFjOBV1NmK", 1999, "eur"),
    ("yearly", "1y", "Yearly", "yearly", "price_1TUvY81FJ9pFBGpFj9fmc6sN", 2999, "eur"),
)


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("billing_period", sa.String(length=32), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("licensed_chats_limit", sa.Integer(), nullable=False),
        sa.Column("closed_games_30d_limit", sa.Integer(), nullable=False),
        sa.Column("unique_players_30d_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"], unique=True)
    op.create_index("ix_subscription_plans_alias", "subscription_plans", ["alias"], unique=True)
    op.create_index("ix_subscription_plans_billing_period", "subscription_plans", ["billing_period"], unique=False)
    op.create_index("ix_subscription_plans_is_active", "subscription_plans", ["is_active"], unique=False)
    op.create_unique_constraint("uq_subscription_plans_stripe_price_id", "subscription_plans", ["stripe_price_id"])

    plans_table = sa.table(
        "subscription_plans",
        sa.column("code", sa.String()),
        sa.column("alias", sa.String()),
        sa.column("title", sa.String()),
        sa.column("billing_period", sa.String()),
        sa.column("stripe_price_id", sa.String()),
        sa.column("amount_minor", sa.Integer()),
        sa.column("currency", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("licensed_chats_limit", sa.Integer()),
        sa.column("closed_games_30d_limit", sa.Integer()),
        sa.column("unique_players_30d_limit", sa.Integer()),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "code": code,
                "alias": alias,
                "title": title,
                "billing_period": billing_period,
                "stripe_price_id": stripe_price_id,
                "amount_minor": amount_minor,
                "currency": currency,
                "is_active": True,
                "licensed_chats_limit": 1,
                "closed_games_30d_limit": 50,
                "unique_players_30d_limit": 30,
            }
            for code, alias, title, billing_period, stripe_price_id, amount_minor, currency in PLAN_ROWS
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_subscription_plans_stripe_price_id", "subscription_plans", type_="unique")
    op.drop_index("ix_subscription_plans_is_active", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_billing_period", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_alias", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_table("subscription_plans")
