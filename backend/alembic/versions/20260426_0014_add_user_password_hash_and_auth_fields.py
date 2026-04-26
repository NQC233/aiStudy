"""add user password hash and auth fields

Revision ID: 20260426_0014
Revises: 20260414_0013
Create Date: 2026-04-26 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260426_0014"
down_revision = "20260414_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
