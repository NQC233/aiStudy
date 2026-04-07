"""add tts and playback fields to presentations

Revision ID: 20260406_0010
Revises: 20260401_0009
Create Date: 2026-04-06 13:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260406_0010"
down_revision = "20260401_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "presentations",
        sa.Column(
            "tts_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "presentations",
        sa.Column(
            "playback_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("presentations", "playback_plan")
    op.drop_column("presentations", "tts_manifest")
