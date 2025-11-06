"""add requester_name column to ticket_history

Revision ID: 007
Revises: 006
Create Date: 2025-11-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    """Add requester_name column to ticket history"""
    op.add_column(
        'ticket_history',
        sa.Column('requester_name', sa.String(length=255), nullable=True),
    )


def downgrade():
    op.drop_column('ticket_history', 'requester_name')
