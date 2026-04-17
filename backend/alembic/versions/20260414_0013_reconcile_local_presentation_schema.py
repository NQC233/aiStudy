"""reconcile local presentation schema drift

Revision ID: 20260414_0013
Revises: 20260406_0010
Create Date: 2026-04-14 23:40:00
"""

from __future__ import annotations


revision = "20260414_0013"
down_revision = "20260406_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historical local environments were stamped to this revision, but the
    # migration file was not committed. Keep this bridge revision as a no-op so
    # Alembic can continue upgrading both fresh and drifted databases.
    return None


def downgrade() -> None:
    return None
