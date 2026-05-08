"""limit boost products and purchases

Revision ID: 20260509_000012
Revises: 20260508_000011
Create Date: 2026-05-09 00:00:12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_000012"
down_revision = "20260508_000011"
branch_labels = None
depends_on = None


BOOST_ROWS = (
    ("boost_30d", "1m", "Limit Boost 30 days", 30, "price_1TUvbj1FJ9pFBGpFBpQcBYdy", 299, "eur"),
    ("boost_90d", "3m", "Limit Boost 90 days", 90, "price_1TUvde1FJ9pFBGpFDYLOf1lf", 699, "eur"),
    ("boost_180d", "6m", "Limit Boost 180 days", 180, "price_1TUveQ1FJ9pFBGpFgsmXFQI7", 1199, "eur"),
    ("boost_365d", "1y", "Limit Boost 365 days", 365, "price_1TUven1FJ9pFBGpFOBinwRDi", 1999, "eur"),
)


def upgrade() -> None:
    op.create_table(
        "limit_boost_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("alias", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Numeric(5, 2), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_limit_boost_products_code", "limit_boost_products", ["code"], unique=True)
    op.create_index("ix_limit_boost_products_alias", "limit_boost_products", ["alias"], unique=True)
    op.create_index("ix_limit_boost_products_is_active", "limit_boost_products", ["is_active"], unique=False)
    op.create_unique_constraint("uq_limit_boost_products_stripe_price_id", "limit_boost_products", ["stripe_price_id"])

    op.create_table(
        "chat_limit_boosts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_price_id", sa.String(length=255), nullable=True),
        sa.Column("boost_code", sa.String(length=64), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Numeric(5, 2), nullable=False),
        sa.Column("extra_closed_games_30d_limit", sa.Integer(), nullable=False),
        sa.Column("extra_unique_players_30d_limit", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_chat_limit_boosts_chat_id", "chat_limit_boosts", ["chat_id"], unique=False)
    op.create_index("ix_chat_limit_boosts_owner_telegram_user_id", "chat_limit_boosts", ["owner_telegram_user_id"], unique=False)
    op.create_index("ix_chat_limit_boosts_boost_code", "chat_limit_boosts", ["boost_code"], unique=False)
    op.create_index("ix_chat_limit_boosts_status", "chat_limit_boosts", ["status"], unique=False)
    op.create_index("ix_chat_limit_boosts_expires_at", "chat_limit_boosts", ["expires_at"], unique=False)
    op.create_unique_constraint("uq_chat_limit_boosts_checkout_session_id", "chat_limit_boosts", ["checkout_session_id"])

    products_table = sa.table(
        "limit_boost_products",
        sa.column("code", sa.String()),
        sa.column("alias", sa.String()),
        sa.column("title", sa.String()),
        sa.column("duration_days", sa.Integer()),
        sa.column("multiplier", sa.Numeric()),
        sa.column("stripe_price_id", sa.String()),
        sa.column("amount_minor", sa.Integer()),
        sa.column("currency", sa.String()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        products_table,
        [
            {
                "code": code,
                "alias": alias,
                "title": title,
                "duration_days": duration_days,
                "multiplier": 2,
                "stripe_price_id": stripe_price_id,
                "amount_minor": amount_minor,
                "currency": currency,
                "is_active": True,
            }
            for code, alias, title, duration_days, stripe_price_id, amount_minor, currency in BOOST_ROWS
        ],
    )


def downgrade() -> None:
    op.drop_constraint("uq_chat_limit_boosts_checkout_session_id", "chat_limit_boosts", type_="unique")
    op.drop_index("ix_chat_limit_boosts_expires_at", table_name="chat_limit_boosts")
    op.drop_index("ix_chat_limit_boosts_status", table_name="chat_limit_boosts")
    op.drop_index("ix_chat_limit_boosts_boost_code", table_name="chat_limit_boosts")
    op.drop_index("ix_chat_limit_boosts_owner_telegram_user_id", table_name="chat_limit_boosts")
    op.drop_index("ix_chat_limit_boosts_chat_id", table_name="chat_limit_boosts")
    op.drop_table("chat_limit_boosts")

    op.drop_constraint("uq_limit_boost_products_stripe_price_id", "limit_boost_products", type_="unique")
    op.drop_index("ix_limit_boost_products_is_active", table_name="limit_boost_products")
    op.drop_index("ix_limit_boost_products_alias", table_name="limit_boost_products")
    op.drop_index("ix_limit_boost_products_code", table_name="limit_boost_products")
    op.drop_table("limit_boost_products")
