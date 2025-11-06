"""Add performance indexes

Revision ID: 002
Revises: 001
Create Date: 2025-01-28

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes for frequently queried columns"""

    # Ticket History Indexes
    op.create_index(
        'ix_ticket_history_status_assigned_to',
        'ticket_history',
        ['status', 'assigned_to_id'],
        unique=False
    )
    op.create_index(
        'ix_ticket_history_created_at_status',
        'ticket_history',
        ['created_at', 'status'],
        unique=False
    )
    op.create_index(
        'ix_ticket_history_resolved_at_category',
        'ticket_history',
        ['resolved_at', 'category'],
        unique=False
    )
    op.create_index(
        'ix_ticket_history_team_level_status',
        'ticket_history',
        ['team_level', 'status'],
        unique=False
    )

    # SLA Tracker Indexes
    op.create_index(
        'ix_sla_trackers_status_paused',
        'sla_trackers',
        ['status', 'paused'],
        unique=False
    )
    op.create_index(
        'ix_sla_trackers_resolution_deadline',
        'sla_trackers',
        ['resolution_deadline'],
        unique=False
    )

    # Team Member Indexes
    op.create_index(
        'ix_team_members_active_team_level',
        'team_members',
        ['active', 'team_level'],
        unique=False
    )

    # Escalation Indexes
    op.create_index(
        'ix_escalations_ticket_id_created_at',
        'escalations',
        ['ticket_id', 'escalated_at'],
        unique=False
    )

    # Performance Metrics Indexes
    op.create_index(
        'ix_performance_metrics_date_team_member',
        'performance_metrics',
        ['date', 'team_member_id'],
        unique=False
    )


def downgrade():
    """Remove performance indexes"""

    # Ticket History Indexes
    op.drop_index('ix_ticket_history_status_assigned_to', table_name='ticket_history')
    op.drop_index('ix_ticket_history_created_at_status', table_name='ticket_history')
    op.drop_index('ix_ticket_history_resolved_at_category', table_name='ticket_history')
    op.drop_index('ix_ticket_history_team_level_status', table_name='ticket_history')

    # SLA Tracker Indexes
    op.drop_index('ix_sla_trackers_status_paused', table_name='sla_trackers')
    op.drop_index('ix_sla_trackers_resolution_deadline', table_name='sla_trackers')

    # Team Member Indexes
    op.drop_index('ix_team_members_active_team_level', table_name='team_members')

    # Escalation Indexes
    op.drop_index('ix_escalations_ticket_id_created_at', table_name='escalations')

    # Performance Metrics Indexes
    op.drop_index('ix_performance_metrics_date_team_member', table_name='performance_metrics')
