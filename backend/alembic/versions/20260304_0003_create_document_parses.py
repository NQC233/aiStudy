"""create document parses table

Revision ID: 20260304_0003
Revises: 20260304_0002
Create Date: 2026-03-04 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260304_0003"
down_revision = "20260304_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("parse_error_message", sa.Text(), nullable=True))

    op.create_table(
        "document_parses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="mineru"),
        sa.Column("parse_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("markdown_storage_key", sa.String(length=512), nullable=True),
        sa.Column("json_storage_key", sa.String(length=512), nullable=True),
        sa.Column("raw_response_storage_key", sa.String(length=512), nullable=True),
        sa.Column("parser_meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_parses_asset_id", "document_parses", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_document_parses_asset_id", table_name="document_parses")
    op.drop_table("document_parses")
    op.drop_column("assets", "parse_error_message")
