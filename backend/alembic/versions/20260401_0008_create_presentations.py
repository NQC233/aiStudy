"""create presentations table

Revision ID: 20260401_0008
Revises: 20260312_0007
Create Date: 2026-04-01 23:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0008"
down_revision = "20260312_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "presentations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column(
            "lesson_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "error_meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("active_run_token", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_presentations_asset_id", "presentations", ["asset_id"]
    )
    op.create_index("ix_presentations_status", "presentations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_presentations_status", table_name="presentations")
    op.drop_constraint("uq_presentations_asset_id", "presentations", type_="unique")
    op.drop_table("presentations")
