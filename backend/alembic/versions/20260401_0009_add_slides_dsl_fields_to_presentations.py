"""add slides dsl fields to presentations

Revision ID: 20260401_0009
Revises: 20260401_0008
Create Date: 2026-04-01 23:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260401_0009"
down_revision = "20260401_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "presentations",
        sa.Column("slides_dsl", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "presentations",
        sa.Column(
            "dsl_quality_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "presentations",
        sa.Column(
            "dsl_fix_logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("presentations", "dsl_fix_logs")
    op.drop_column("presentations", "dsl_quality_report")
    op.drop_column("presentations", "slides_dsl")
