"""Add ticket comments table

Revision ID: 003
Revises: 002
Create Date: 2025-10-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    """Create ticket_comments table and add indexes"""

    # Create CommentType enum
    comment_type_enum = ENUM('public', 'internal', name='comment_type', create_type=False)
    comment_type_enum.create(op.get_bind(), checkfirst=True)

    # Create ticket_comments table
    op.create_table(
        'ticket_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('comment_type', comment_type_enum, nullable=False, server_default='public'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('edited', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('has_attachments', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('attachment_count', sa.Integer(), nullable=True, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['ticket_id'], ['ticket_history.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['team_members.id'], ondelete='SET NULL')
    )

    # Create indexes for performance
    op.create_index('ix_ticket_comments_ticket_id', 'ticket_comments', ['ticket_id'], unique=False)
    op.create_index('ix_ticket_comments_author_id', 'ticket_comments', ['author_id'], unique=False)
    op.create_index('ix_ticket_comments_created_at', 'ticket_comments', ['created_at'], unique=False)
    op.create_index('ix_ticket_comments_ticket_id_created_at', 'ticket_comments', ['ticket_id', 'created_at'], unique=False)


def downgrade():
    """Drop ticket_comments table and indexes"""

    # Drop indexes
    op.drop_index('ix_ticket_comments_ticket_id_created_at', table_name='ticket_comments')
    op.drop_index('ix_ticket_comments_created_at', table_name='ticket_comments')
    op.drop_index('ix_ticket_comments_author_id', table_name='ticket_comments')
    op.drop_index('ix_ticket_comments_ticket_id', table_name='ticket_comments')

    # Drop table
    op.drop_table('ticket_comments')

    # Drop enum type
    comment_type_enum = ENUM('public', 'internal', name='comment_type')
    comment_type_enum.drop(op.get_bind(), checkfirst=True)
