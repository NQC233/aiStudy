"""add slide generation v2 fields to presentations

Revision ID: 20260415_0011
Revises: 20260414_0013
Create Date: 2026-04-15 16:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "20260415_0011"
down_revision = "20260414_0013"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("presentations", "analysis_pack"):
        op.add_column(
            "presentations",
            sa.Column(
                "analysis_pack",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if not _has_column("presentations", "visual_asset_catalog"):
        op.add_column(
            "presentations",
            sa.Column(
                "visual_asset_catalog",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    if not _has_column("presentations", "presentation_plan"):
        op.add_column(
            "presentations",
            sa.Column(
                "presentation_plan",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if not _has_column("presentations", "scene_specs"):
        op.add_column(
            "presentations",
            sa.Column(
                "scene_specs",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    if not _has_column("presentations", "rendered_slide_pages"):
        op.add_column(
            "presentations",
            sa.Column(
                "rendered_slide_pages",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )
    if not _has_column("presentations", "runtime_bundle"):
        op.add_column(
            "presentations",
            sa.Column(
                "runtime_bundle",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade() -> None:
    if _has_column("presentations", "runtime_bundle"):
        op.drop_column("presentations", "runtime_bundle")
    if _has_column("presentations", "rendered_slide_pages"):
        op.drop_column("presentations", "rendered_slide_pages")
    if _has_column("presentations", "scene_specs"):
        op.drop_column("presentations", "scene_specs")
    if _has_column("presentations", "presentation_plan"):
        op.drop_column("presentations", "presentation_plan")
    if _has_column("presentations", "visual_asset_catalog"):
        op.drop_column("presentations", "visual_asset_catalog")
    if _has_column("presentations", "analysis_pack"):
        op.drop_column("presentations", "analysis_pack")
