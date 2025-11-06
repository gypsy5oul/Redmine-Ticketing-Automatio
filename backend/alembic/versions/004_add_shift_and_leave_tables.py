"""Add shift assignments and member leaves tables

Revision ID: 004
Revises: 003
Create Date: 2025-11-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Create scheduling tables and enums."""
    # Define enums
    leave_status_enum = sa.Enum(
        'pending', 'approved', 'rejected', 'cancelled',
        name='leave_status'
    )
    leave_type_enum = sa.Enum(
        'vacation', 'sick', 'training', 'unplanned', 'other',
        name='leave_type'
    )

    bind = op.get_bind()
    leave_status_enum.create(bind, checkfirst=True)
    leave_type_enum.create(bind, checkfirst=True)

    # shift_assignments table
    op.create_table(
        'shift_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=False),
        sa.Column('team_level', sa.String(length=10), nullable=True),
        sa.Column('day_of_week', sa.SmallInteger(), nullable=True),
        sa.Column('start_hour', sa.SmallInteger(), nullable=False),
        sa.Column('start_minute', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('end_hour', sa.SmallInteger(), nullable=False),
        sa.Column('end_minute', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('priority', sa.SmallInteger(), nullable=False, server_default='50'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shift_assignments_member', 'shift_assignments', ['team_member_id'], False)
    op.create_index('ix_shift_assignments_active', 'shift_assignments', ['is_active'], False)
    op.create_index('ix_shift_assignments_day', 'shift_assignments', ['day_of_week'], False)

    # member_leaves table
    op.create_table(
        'member_leaves',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('leave_type', leave_type_enum, nullable=False, server_default='other'),
        sa.Column('status', leave_status_enum, nullable=False, server_default='approved'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=200), nullable=True),
        sa.Column('approved_by', sa.String(length=200), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_member_leaves_member', 'member_leaves', ['team_member_id'], False)
    op.create_index('ix_member_leaves_status', 'member_leaves', ['status'], False)
    op.create_index('ix_member_leaves_start_date', 'member_leaves', ['start_date'], False)


def downgrade():
    """Drop scheduling tables and enums."""
    op.drop_index('ix_member_leaves_start_date', table_name='member_leaves')
    op.drop_index('ix_member_leaves_status', table_name='member_leaves')
    op.drop_index('ix_member_leaves_member', table_name='member_leaves')
    op.drop_table('member_leaves')

    op.drop_index('ix_shift_assignments_day', table_name='shift_assignments')
    op.drop_index('ix_shift_assignments_active', table_name='shift_assignments')
    op.drop_index('ix_shift_assignments_member', table_name='shift_assignments')
    op.drop_table('shift_assignments')

    bind = op.get_bind()
    leave_status_enum = sa.Enum(
        'pending', 'approved', 'rejected', 'cancelled',
        name='leave_status'
    )
    leave_type_enum = sa.Enum(
        'vacation', 'sick', 'training', 'unplanned', 'other',
        name='leave_type'
    )
    leave_status_enum.drop(bind, checkfirst=True)
    leave_type_enum.drop(bind, checkfirst=True)

