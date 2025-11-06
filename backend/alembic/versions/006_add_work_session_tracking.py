"""add work session tracking

Revision ID: 006
Revises: 005
Create Date: 2025-11-01 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add work session tracking tables and fields"""

    # Create work_sessions table
    op.create_table(
        'work_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=False),
        sa.Column('session_type', sa.String(length=50), nullable=False, server_default='active_work'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('paused_reason', sa.String(length=200), nullable=True),
        sa.Column('session_number', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['ticket_id'], ['ticket_history.id'], ),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_work_sessions_id', 'work_sessions', ['id'], unique=False)
    op.create_index('ix_work_sessions_ticket_id', 'work_sessions', ['ticket_id'], unique=False)
    op.create_index('ix_work_sessions_team_member_id', 'work_sessions', ['team_member_id'], unique=False)
    op.create_index('ix_work_sessions_session_type', 'work_sessions', ['session_type'], unique=False)
    op.create_index('ix_work_sessions_is_active', 'work_sessions', ['is_active'], unique=False)
    op.create_index('ix_work_sessions_started_at', 'work_sessions', ['started_at'], unique=False)
    op.create_index('ix_work_sessions_ended_at', 'work_sessions', ['ended_at'], unique=False)

    # Create engineer_work_status table
    op.create_table(
        'engineer_work_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('team_member_id', sa.Integer(), nullable=False),
        sa.Column('active_work_sessions_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('assigned_tickets_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_idle', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('idle_since', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_idle_minutes_today', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('can_accept_work', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('max_concurrent_sessions', sa.Integer(), nullable=True, server_default='2'),
        sa.Column('work_started_today_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_work_minutes_today', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_waiting_minutes_today', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tickets_completed_today', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['team_member_id'], ['team_members.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_member_id')
    )
    op.create_index('ix_engineer_work_status_id', 'engineer_work_status', ['id'], unique=False)
    op.create_index('ix_engineer_work_status_team_member_id', 'engineer_work_status', ['team_member_id'], unique=True)
    op.create_index('ix_engineer_work_status_is_idle', 'engineer_work_status', ['is_idle'], unique=False)

    # Add work tracking fields to ticket_history table
    op.add_column('ticket_history', sa.Column('work_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ticket_history', sa.Column('last_work_session_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ticket_history', sa.Column('total_work_minutes', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('ticket_history', sa.Column('total_waiting_minutes', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('ticket_history', sa.Column('total_idle_minutes', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('ticket_history', sa.Column('active_work_session_id', sa.Integer(), nullable=True))
    op.add_column('ticket_history', sa.Column('work_efficiency_percent', sa.Float(), nullable=True))

    # Create indexes for work tracking fields
    op.create_index('ix_ticket_history_work_started_at', 'ticket_history', ['work_started_at'], unique=False)
    op.create_index('ix_ticket_history_last_work_session_at', 'ticket_history', ['last_work_session_at'], unique=False)


def downgrade():
    """Remove work session tracking tables and fields"""

    # Drop indexes from ticket_history
    op.drop_index('ix_ticket_history_last_work_session_at', table_name='ticket_history')
    op.drop_index('ix_ticket_history_work_started_at', table_name='ticket_history')

    # Drop columns from ticket_history
    op.drop_column('ticket_history', 'work_efficiency_percent')
    op.drop_column('ticket_history', 'active_work_session_id')
    op.drop_column('ticket_history', 'total_idle_minutes')
    op.drop_column('ticket_history', 'total_waiting_minutes')
    op.drop_column('ticket_history', 'total_work_minutes')
    op.drop_column('ticket_history', 'last_work_session_at')
    op.drop_column('ticket_history', 'work_started_at')

    # Drop engineer_work_status table
    op.drop_index('ix_engineer_work_status_is_idle', table_name='engineer_work_status')
    op.drop_index('ix_engineer_work_status_team_member_id', table_name='engineer_work_status')
    op.drop_index('ix_engineer_work_status_id', table_name='engineer_work_status')
    op.drop_table('engineer_work_status')

    # Drop work_sessions table
    op.drop_index('ix_work_sessions_ended_at', table_name='work_sessions')
    op.drop_index('ix_work_sessions_started_at', table_name='work_sessions')
    op.drop_index('ix_work_sessions_is_active', table_name='work_sessions')
    op.drop_index('ix_work_sessions_session_type', table_name='work_sessions')
    op.drop_index('ix_work_sessions_team_member_id', table_name='work_sessions')
    op.drop_index('ix_work_sessions_ticket_id', table_name='work_sessions')
    op.drop_index('ix_work_sessions_id', table_name='work_sessions')
    op.drop_table('work_sessions')
