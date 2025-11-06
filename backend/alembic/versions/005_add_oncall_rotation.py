"""Add on-call rotation tables and shift metadata

Revision ID: 005
Revises: 004
Create Date: 2025-11-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('shift_assignments', sa.Column('category', sa.String(length=20), nullable=True, server_default='standard'))
    op.add_column('shift_assignments', sa.Column('generated_week_start', sa.Date(), nullable=True))
    op.create_index('ix_shift_assignments_category', 'shift_assignments', ['category'], unique=False)

    op.create_table(
        'oncall_rotation_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_level', sa.String(length=10), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_oncall_rotation_entries_team_level', 'oncall_rotation_entries', ['team_level'], unique=False)
    op.create_index('ix_oncall_rotation_entries_member', 'oncall_rotation_entries', ['team_member_id'], unique=False)
    op.create_index('ix_oncall_rotation_entries_active', 'oncall_rotation_entries', ['active'], unique=False)

    op.create_table(
        'oncall_rotation_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_level', sa.String(length=10), nullable=False),
        sa.Column('next_position', sa.SmallInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_level', name='uq_oncall_rotation_state_team_level')
    )

    op.create_table(
        'oncall_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_level', sa.String(length=10), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=True),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('week_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='scheduled'),
        sa.Column('rotation_position', sa.SmallInteger(), nullable=True),
        sa.Column('replaced_by_member_id', sa.Integer(), nullable=True),
        sa.Column('replaces_assignment_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['replaced_by_member_id'], ['team_members.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['replaces_assignment_id'], ['oncall_assignments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_oncall_assignments_team_level', 'oncall_assignments', ['team_level'], unique=False)
    op.create_index('ix_oncall_assignments_week', 'oncall_assignments', ['week_start'], unique=False)
    op.create_index('ix_oncall_assignments_status', 'oncall_assignments', ['status'], unique=False)

    # Update existing rows default
    op.execute("UPDATE shift_assignments SET category='standard' WHERE category IS NULL")


def downgrade():
    op.drop_index('ix_oncall_assignments_status', table_name='oncall_assignments')
    op.drop_index('ix_oncall_assignments_week', table_name='oncall_assignments')
    op.drop_index('ix_oncall_assignments_team_level', table_name='oncall_assignments')
    op.drop_table('oncall_assignments')

    op.drop_table('oncall_rotation_state')

    op.drop_index('ix_oncall_rotation_entries_active', table_name='oncall_rotation_entries')
    op.drop_index('ix_oncall_rotation_entries_member', table_name='oncall_rotation_entries')
    op.drop_index('ix_oncall_rotation_entries_team_level', table_name='oncall_rotation_entries')
    op.drop_table('oncall_rotation_entries')

    op.drop_index('ix_shift_assignments_category', table_name='shift_assignments')
    op.drop_column('shift_assignments', 'generated_week_start')
    op.drop_column('shift_assignments', 'category')
