"""create anchors and notes tables

Revision ID: 20260312_0007
Revises: 20260309_0006
Create Date: 2026-03-12 20:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260312_0007"
down_revision = "20260309_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anchors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("anchor_type", sa.String(length=32), nullable=False, server_default="text_selection"),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("block_id", sa.String(length=128), nullable=True),
        sa.Column("paragraph_no", sa.Integer(), nullable=True),
        sa.Column("selected_text", sa.Text(), nullable=True),
        sa.Column("selector_type", sa.String(length=64), nullable=False, server_default="block"),
        sa.Column(
            "selector_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_anchors_asset_id", "anchors", ["asset_id"])
    op.create_index("ix_anchors_user_id", "anchors", ["user_id"])
    op.create_index("ix_anchors_anchor_type", "anchors", ["anchor_type"])
    op.create_index("ix_anchors_page_no", "anchors", ["page_no"])
    op.create_index("ix_anchors_block_id", "anchors", ["block_id"])

    op.create_table(
        "notes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("anchor_id", sa.String(length=36), sa.ForeignKey("anchors.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notes_asset_id", "notes", ["asset_id"])
    op.create_index("ix_notes_user_id", "notes", ["user_id"])
    op.create_index("ix_notes_anchor_id", "notes", ["anchor_id"])
    op.create_index("ix_notes_created_at", "notes", ["created_at"])
    op.create_index("ix_notes_updated_at", "notes", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_notes_updated_at", table_name="notes")
    op.drop_index("ix_notes_created_at", table_name="notes")
    op.drop_index("ix_notes_anchor_id", table_name="notes")
    op.drop_index("ix_notes_user_id", table_name="notes")
    op.drop_index("ix_notes_asset_id", table_name="notes")
    op.drop_table("notes")

    op.drop_index("ix_anchors_block_id", table_name="anchors")
    op.drop_index("ix_anchors_page_no", table_name="anchors")
    op.drop_index("ix_anchors_anchor_type", table_name="anchors")
    op.drop_index("ix_anchors_user_id", table_name="anchors")
    op.drop_index("ix_anchors_asset_id", table_name="anchors")
    op.drop_table("anchors")
