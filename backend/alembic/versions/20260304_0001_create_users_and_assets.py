"""create users and assets tables

Revision ID: 20260304_0001
Revises:
Create Date: 2026-03-04 20:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260304_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("parse_status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("kb_status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("mindmap_status", sa.String(length=32), nullable=False, server_default="not_started"),
        sa.Column("slides_status", sa.String(length=32), nullable=False, server_default="not_generated"),
        sa.Column("anki_status", sa.String(length=32), nullable=False, server_default="not_generated"),
        sa.Column("quiz_status", sa.String(length=32), nullable=False, server_default="not_generated"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_assets_user_id", "assets", ["user_id"])
    op.create_index("ix_assets_created_at", "assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_assets_created_at", table_name="assets")
    op.drop_index("ix_assets_user_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("users")
