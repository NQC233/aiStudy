"""create mindmaps and mindmap_nodes tables

Revision ID: 20260309_0006
Revises: 20260309_0005
Create Date: 2026-03-09 23:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260309_0006"
down_revision = "20260309_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mindmaps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mindmaps_asset_id", "mindmaps", ["asset_id"])
    op.create_index("ix_mindmaps_status", "mindmaps", ["status"])
    op.create_unique_constraint("uq_mindmaps_asset_version", "mindmaps", ["asset_id", "version"])

    op.create_table(
        "mindmap_nodes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mindmap_id", sa.String(length=36), sa.ForeignKey("mindmaps.id"), nullable=False),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("mindmap_nodes.id"), nullable=True),
        sa.Column("node_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_no", sa.Integer(), nullable=True),
        sa.Column("paragraph_ref", sa.String(length=64), nullable=True),
        sa.Column(
            "section_path",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "block_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "selector_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mindmap_nodes_mindmap_id", "mindmap_nodes", ["mindmap_id"])
    op.create_index("ix_mindmap_nodes_parent_id", "mindmap_nodes", ["parent_id"])
    op.create_index("ix_mindmap_nodes_page_no", "mindmap_nodes", ["page_no"])
    op.create_unique_constraint("uq_mindmap_nodes_mindmap_node_key", "mindmap_nodes", ["mindmap_id", "node_key"])


def downgrade() -> None:
    op.drop_constraint("uq_mindmap_nodes_mindmap_node_key", "mindmap_nodes", type_="unique")
    op.drop_index("ix_mindmap_nodes_page_no", table_name="mindmap_nodes")
    op.drop_index("ix_mindmap_nodes_parent_id", table_name="mindmap_nodes")
    op.drop_index("ix_mindmap_nodes_mindmap_id", table_name="mindmap_nodes")
    op.drop_table("mindmap_nodes")

    op.drop_constraint("uq_mindmaps_asset_version", "mindmaps", type_="unique")
    op.drop_index("ix_mindmaps_status", table_name="mindmaps")
    op.drop_index("ix_mindmaps_asset_id", table_name="mindmaps")
    op.drop_table("mindmaps")
