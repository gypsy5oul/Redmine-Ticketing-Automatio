"""Initial database schema (baseline)

Revision ID: 001
Revises:
Create Date: 2025-01-01

This is a baseline migration that assumes tables already exist.
It marks the starting point for alembic migrations.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """
    Baseline migration - tables already exist
    This migration does nothing as tables were created manually
    """
    pass


def downgrade():
    """
    Baseline migration - cannot downgrade from initial state
    """
    pass
