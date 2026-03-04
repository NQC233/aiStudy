"""create asset files table

Revision ID: 20260304_0002
Revises: 20260304_0001
Create Date: 2026-03-04 20:50:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260304_0002"
down_revision = "20260304_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asset_files",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("public_url", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_asset_files_asset_id", "asset_files", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_asset_files_asset_id", table_name="asset_files")
    op.drop_table("asset_files")
