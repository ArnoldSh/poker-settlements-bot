"""subscription status granularity

Revision ID: 20260508_000011
Revises: 20260508_000010
Create Date: 2026-05-08 00:00:11
"""
from __future__ import annotations

from alembic import op


revision = "20260508_000011"
down_revision = "20260508_000010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_subscriptions
        SET status = provider_status
        WHERE status = 'payment_problem'
          AND provider_status IN ('past_due', 'paused', 'unpaid')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE user_subscriptions
        SET status = 'payment_problem'
        WHERE status IN ('past_due', 'paused', 'unpaid')
        """
    )
