"""stripe event object fields

Revision ID: 20260417_000004
Revises: 20260417_000003
Create Date: 2026-04-17 00:00:04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_000004"
down_revision = "20260417_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("stripe_events", "payload_json")
    op.add_column("stripe_events", sa.Column("object_type", sa.String(length=255), nullable=True))
    op.add_column("stripe_events", sa.Column("object_reference_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("stripe_events", "object_reference_id")
    op.drop_column("stripe_events", "object_type")
    op.add_column("stripe_events", sa.Column("payload_json", sa.Text(), nullable=False))
