"""catalog price snapshots

Revision ID: 20260509_000013
Revises: 20260509_000012
Create Date: 2026-05-09 00:00:13
"""
from __future__ import annotations

from alembic import op


revision = "20260509_000013"
down_revision = "20260509_000012"
branch_labels = None
depends_on = None


PLAN_ROWS = (
    ("monthly", "price_1TOk3X1FJ9pFBGpFYWPsPZ6c", 499, "eur"),
    ("quarterly", "price_1TUvW91FJ9pFBGpFQZfLLvFp", 999, "eur"),
    ("semiannual", "price_1TUvXk1FJ9pFBGpFjOBV1NmK", 1999, "eur"),
    ("yearly", "price_1TUvY81FJ9pFBGpFj9fmc6sN", 2999, "eur"),
)

BOOST_ROWS = (
    ("boost_30d", "price_1TUvbj1FJ9pFBGpFBpQcBYdy", 299, "eur"),
    ("boost_90d", "price_1TUvde1FJ9pFBGpFDYLOf1lf", 699, "eur"),
    ("boost_180d", "price_1TUveQ1FJ9pFBGpFgsmXFQI7", 1199, "eur"),
    ("boost_365d", "price_1TUven1FJ9pFBGpFOBinwRDi", 1999, "eur"),
)


def _quote(value: str) -> str:
    return value.replace("'", "''")


def upgrade() -> None:
    op.execute("ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS amount_minor INTEGER")
    op.execute("ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS currency VARCHAR(3)")
    op.execute("ALTER TABLE limit_boost_products ADD COLUMN IF NOT EXISTS amount_minor INTEGER")
    op.execute("ALTER TABLE limit_boost_products ADD COLUMN IF NOT EXISTS currency VARCHAR(3)")

    for code, stripe_price_id, amount_minor, currency in PLAN_ROWS:
        op.execute(
            f"""
            UPDATE subscription_plans
            SET stripe_price_id = '{_quote(stripe_price_id)}',
                amount_minor = {amount_minor},
                currency = '{_quote(currency)}'
            WHERE code = '{_quote(code)}'
            """
        )

    for code, stripe_price_id, amount_minor, currency in BOOST_ROWS:
        op.execute(
            f"""
            UPDATE limit_boost_products
            SET stripe_price_id = '{_quote(stripe_price_id)}',
                amount_minor = {amount_minor},
                currency = '{_quote(currency)}'
            WHERE code = '{_quote(code)}'
            """
        )


def downgrade() -> None:
    op.execute("ALTER TABLE limit_boost_products DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE limit_boost_products DROP COLUMN IF EXISTS amount_minor")
    op.execute("ALTER TABLE subscription_plans DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE subscription_plans DROP COLUMN IF EXISTS amount_minor")
