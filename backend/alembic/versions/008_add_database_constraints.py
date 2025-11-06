"""Add database constraints and indexes for data integrity

Revision ID: 008
Revises: 007
Create Date: 2025-11-04 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """Add critical database constraints and indexes"""

    # ============================================================================
    # CHECK CONSTRAINTS - Data Validation
    # ============================================================================

    # 1. Team Members - Work hours validation
    op.execute("""
        ALTER TABLE team_members
        ADD CONSTRAINT chk_work_hours
        CHECK (
            work_start_hour >= 0 AND work_start_hour < 24
            AND work_end_hour > 0 AND work_end_hour <= 24
            AND work_end_hour > work_start_hour
        );
    """)

    op.execute("""
        ALTER TABLE team_members
        ADD CONSTRAINT chk_max_tickets_positive
        CHECK (max_tickets > 0);
    """)

    # 2. Performance Metrics - Percentage validation
    op.execute("""
        ALTER TABLE performance_metrics
        ADD CONSTRAINT chk_percentages
        CHECK (
            sla_compliance_rate >= 0 AND sla_compliance_rate <= 100
            AND reopened_rate >= 0 AND reopened_rate <= 100
            AND first_time_resolution_rate >= 0 AND first_time_resolution_rate <= 100
        );
    """)

    op.execute("""
        ALTER TABLE performance_metrics
        ADD CONSTRAINT chk_satisfaction_score
        CHECK (customer_satisfaction_score >= 1 AND customer_satisfaction_score <= 5);
    """)

    # 3. Ticket History - Temporal ordering and probability ranges
    op.execute("""
        ALTER TABLE ticket_history
        ADD CONSTRAINT chk_ticket_dates
        CHECK (
            (assigned_at IS NULL OR assigned_at >= created_at)
            AND (first_response_at IS NULL OR first_response_at >= created_at)
            AND (resolved_at IS NULL OR resolved_at >= created_at)
            AND (closed_at IS NULL OR (resolved_at IS NULL OR closed_at >= resolved_at))
        );
    """)

    op.execute("""
        ALTER TABLE ticket_history
        ADD CONSTRAINT chk_escalation_probability
        CHECK (
            predicted_escalation_probability IS NULL
            OR (predicted_escalation_probability >= 0 AND predicted_escalation_probability <= 1)
        );
    """)

    op.execute("""
        ALTER TABLE ticket_history
        ADD CONSTRAINT chk_ml_confidence
        CHECK (
            ml_confidence_score IS NULL
            OR (ml_confidence_score >= 0 AND ml_confidence_score <= 1)
        );
    """)

    op.execute("""
        ALTER TABLE ticket_history
        ADD CONSTRAINT chk_work_efficiency
        CHECK (
            work_efficiency_percent IS NULL
            OR (work_efficiency_percent >= 0 AND work_efficiency_percent <= 100)
        );
    """)

    # 4. Business Hours - Hour validation
    op.execute("""
        ALTER TABLE business_hours
        ADD CONSTRAINT chk_business_hours
        CHECK (
            start_hour >= 0 AND start_hour < 24
            AND end_hour > 0 AND end_hour <= 24
        );
    """)

    # 5. Shift Assignments - Hour and minute validation
    op.execute("""
        ALTER TABLE shift_assignments
        ADD CONSTRAINT chk_shift_hours
        CHECK (
            start_hour >= 0 AND start_hour < 24
            AND end_hour >= 0 AND end_hour <= 24
            AND start_minute >= 0 AND start_minute < 60
            AND end_minute >= 0 AND end_minute < 60
        );
    """)

    op.execute("""
        ALTER TABLE shift_assignments
        ADD CONSTRAINT chk_day_of_week
        CHECK (day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6));
    """)

    op.execute("""
        ALTER TABLE shift_assignments
        ADD CONSTRAINT chk_effective_dates
        CHECK (effective_to IS NULL OR effective_to >= effective_from);
    """)

    # 6. Member Leaves - Date validation
    op.execute("""
        ALTER TABLE member_leaves
        ADD CONSTRAINT chk_leave_dates
        CHECK (end_date >= start_date);
    """)

    # 7. Work Sessions - Session validation
    op.execute("""
        ALTER TABLE work_sessions
        ADD CONSTRAINT chk_session_duration
        CHECK (ended_at IS NULL OR ended_at >= started_at);
    """)

    op.execute("""
        ALTER TABLE work_sessions
        ADD CONSTRAINT chk_session_active_ended
        CHECK (NOT (is_active = true AND ended_at IS NOT NULL));
    """)

    # 8. Engineer Work Status - Capacity validation
    op.execute("""
        ALTER TABLE engineer_work_status
        ADD CONSTRAINT chk_active_sessions
        CHECK (
            active_work_sessions_count >= 0
            AND active_work_sessions_count <= max_concurrent_sessions
        );
    """)

    # 9. Ticket Resolution Metrics - Rating validation
    op.execute("""
        ALTER TABLE ticket_resolution_metrics
        ADD CONSTRAINT chk_satisfaction_rating
        CHECK (
            customer_satisfaction IS NULL
            OR (customer_satisfaction >= 1 AND customer_satisfaction <= 5)
        );
    """)

    # 10. On-Call Assignments - Week validation
    op.execute("""
        ALTER TABLE oncall_assignments
        ADD CONSTRAINT chk_oncall_week
        CHECK (week_end >= week_start);
    """)

    # ============================================================================
    # UNIQUE CONSTRAINTS - Prevent Duplicates
    # ============================================================================

    # 1. Performance Metrics - One record per member per day
    op.execute("""
        ALTER TABLE performance_metrics
        ADD CONSTRAINT uq_member_date
        UNIQUE (team_member_id, date);
    """)

    # ============================================================================
    # COMPOSITE INDEXES - Query Performance
    # ============================================================================

    # 1. Ticket History - Assignment and status queries
    op.create_index(
        'idx_ticket_assigned_status',
        'ticket_history',
        ['assigned_to_id', 'status']
    )

    # 2. Ticket History - Priority and status queries
    op.create_index(
        'idx_ticket_priority_status',
        'ticket_history',
        ['priority', 'status']
    )

    # 3. Ticket History - Team level and status queries
    op.create_index(
        'idx_ticket_team_status',
        'ticket_history',
        ['team_level', 'status']
    )

    # 4. Ticket History - Created date range queries with status
    op.create_index(
        'idx_ticket_created_status',
        'ticket_history',
        ['created_at', 'status']
    )

    # 5. Performance Metrics - Member and date (composite)
    op.create_index(
        'idx_perf_member_date',
        'performance_metrics',
        ['team_member_id', 'date']
    )

    # 6. Work Sessions - Member and started time
    op.create_index(
        'idx_work_session_member_started',
        'work_sessions',
        ['team_member_id', 'started_at']
    )

    # 7. Work Sessions - Ticket and started time
    op.create_index(
        'idx_work_session_ticket_started',
        'work_sessions',
        ['ticket_id', 'started_at']
    )

    # 8. Work Sessions - Partial index for active sessions only
    op.execute("""
        CREATE INDEX idx_work_session_active
        ON work_sessions(team_member_id, is_active)
        WHERE is_active = true;
    """)

    # 9. SLA Breaches - Priority and breach date for reporting
    op.create_index(
        'idx_sla_breach_priority_date',
        'sla_breaches',
        ['priority', 'breached_at']
    )

    # 10. SLA Breaches - Team level and breach date
    op.create_index(
        'idx_sla_breach_team_date',
        'sla_breaches',
        ['team_level', 'breached_at']
    )

    # 11. SLA Breaches - Assigned member for performance tracking
    op.create_index(
        'idx_sla_breach_assigned',
        'sla_breaches',
        ['assigned_to_id']
    )

    # 12. On-Call Assignments - Team level and week start
    op.create_index(
        'idx_oncall_team_week',
        'oncall_assignments',
        ['team_level', 'week_start']
    )

    # 13. On-Call Assignments - Member and week start
    op.create_index(
        'idx_oncall_member_week',
        'oncall_assignments',
        ['team_member_id', 'week_start']
    )

    # 14. Shift Assignments - Member, day, and active status
    op.create_index(
        'idx_shift_member_day_active',
        'shift_assignments',
        ['team_member_id', 'day_of_week', 'is_active']
    )

    # 15. Activities - Created date for time-based queries
    op.create_index(
        'idx_activity_created',
        'activities',
        ['created_at']
    )

    # 16. Activities - Activity type for filtering
    op.create_index(
        'idx_activity_type',
        'activities',
        ['activity_type']
    )

    # 17. Escalations - Reason and date for analytics
    op.create_index(
        'idx_escalation_reason_date',
        'escalations',
        ['reason', 'escalated_at']
    )

    # 18. SLA Trackers - Partial index for active SLAs (not breached)
    op.execute("""
        CREATE INDEX idx_sla_tracker_active
        ON sla_trackers(status, updated_at)
        WHERE status != 'BREACHED';
    """)

    # 19. Ticket Collaborations - Ticket ID for collaboration queries
    op.create_index(
        'idx_collaboration_ticket',
        'ticket_collaborations',
        ['ticket_id']
    )

    # 20. Ticket Comments - Ticket ID and created date
    op.create_index(
        'idx_comment_ticket_created',
        'ticket_comments',
        ['ticket_id', 'created_at']
    )


def downgrade():
    """Remove constraints and indexes"""

    # Drop indexes
    op.drop_index('idx_comment_ticket_created', 'ticket_comments')
    op.drop_index('idx_collaboration_ticket', 'ticket_collaborations')
    op.drop_index('idx_sla_tracker_active', 'sla_trackers')
    op.drop_index('idx_escalation_reason_date', 'escalations')
    op.drop_index('idx_activity_type', 'activities')
    op.drop_index('idx_activity_created', 'activities')
    op.drop_index('idx_shift_member_day_active', 'shift_assignments')
    op.drop_index('idx_oncall_member_week', 'oncall_assignments')
    op.drop_index('idx_oncall_team_week', 'oncall_assignments')
    op.drop_index('idx_sla_breach_assigned', 'sla_breaches')
    op.drop_index('idx_sla_breach_team_date', 'sla_breaches')
    op.drop_index('idx_sla_breach_priority_date', 'sla_breaches')
    op.drop_index('idx_work_session_active', 'work_sessions')
    op.drop_index('idx_work_session_ticket_started', 'work_sessions')
    op.drop_index('idx_work_session_member_started', 'work_sessions')
    op.drop_index('idx_perf_member_date', 'performance_metrics')
    op.drop_index('idx_ticket_created_status', 'ticket_history')
    op.drop_index('idx_ticket_team_status', 'ticket_history')
    op.drop_index('idx_ticket_priority_status', 'ticket_history')
    op.drop_index('idx_ticket_assigned_status', 'ticket_history')

    # Drop unique constraints
    op.execute("ALTER TABLE performance_metrics DROP CONSTRAINT uq_member_date;")

    # Drop CHECK constraints
    op.execute("ALTER TABLE oncall_assignments DROP CONSTRAINT chk_oncall_week;")
    op.execute("ALTER TABLE ticket_resolution_metrics DROP CONSTRAINT chk_satisfaction_rating;")
    op.execute("ALTER TABLE engineer_work_status DROP CONSTRAINT chk_active_sessions;")
    op.execute("ALTER TABLE work_sessions DROP CONSTRAINT chk_session_active_ended;")
    op.execute("ALTER TABLE work_sessions DROP CONSTRAINT chk_session_duration;")
    op.execute("ALTER TABLE member_leaves DROP CONSTRAINT chk_leave_dates;")
    op.execute("ALTER TABLE shift_assignments DROP CONSTRAINT chk_effective_dates;")
    op.execute("ALTER TABLE shift_assignments DROP CONSTRAINT chk_day_of_week;")
    op.execute("ALTER TABLE shift_assignments DROP CONSTRAINT chk_shift_hours;")
    op.execute("ALTER TABLE business_hours DROP CONSTRAINT chk_business_hours;")
    op.execute("ALTER TABLE ticket_history DROP CONSTRAINT chk_work_efficiency;")
    op.execute("ALTER TABLE ticket_history DROP CONSTRAINT chk_ml_confidence;")
    op.execute("ALTER TABLE ticket_history DROP CONSTRAINT chk_escalation_probability;")
    op.execute("ALTER TABLE ticket_history DROP CONSTRAINT chk_ticket_dates;")
    op.execute("ALTER TABLE performance_metrics DROP CONSTRAINT chk_satisfaction_score;")
    op.execute("ALTER TABLE performance_metrics DROP CONSTRAINT chk_percentages;")
    op.execute("ALTER TABLE team_members DROP CONSTRAINT chk_max_tickets_positive;")
    op.execute("ALTER TABLE team_members DROP CONSTRAINT chk_work_hours;")
