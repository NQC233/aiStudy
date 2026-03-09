"""create document chunks table

Revision ID: 20260305_0004
Revises: 20260304_0003
Create Date: 2026-03-05 22:10:00
"""

from __future__ import annotations

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260305_0004"
down_revision = "20260304_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("parse_id", sa.String(length=36), sa.ForeignKey("document_parses.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "section_path",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("paragraph_start", sa.Integer(), nullable=True),
        sa.Column("paragraph_end", sa.Integer(), nullable=True),
        sa.Column(
            "block_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_document_chunks_asset_id", "document_chunks", ["asset_id"])
    op.create_index("ix_document_chunks_parse_id", "document_chunks", ["parse_id"])
    op.create_index("ix_document_chunks_embedding_status", "document_chunks", ["embedding_status"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_status", table_name="document_chunks")
    op.drop_index("ix_document_chunks_parse_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_asset_id", table_name="document_chunks")
    op.drop_table("document_chunks")
