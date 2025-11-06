-- ============================================================================
-- PERFORMANCE OPTIMIZATION: Add Missing Database Indexes
-- ============================================================================
-- Created: 2025-10-30
-- Purpose: Improve query performance for filtering, sorting, and JOIN operations
--
-- These indexes address:
-- 1. Slow filtering on frequently used columns
-- 2. Slow sorting operations
-- 3. Inefficient JOIN operations
-- 4. Time-based queries
-- ============================================================================

-- Ticket History Performance Indexes
-- -----------------------------------

-- Index for updated_at (used in sorting and time-based queries)
CREATE INDEX IF NOT EXISTS idx_ticket_history_updated_at
ON ticket_history(updated_at DESC);

-- Index for environment (frequently filtered)
CREATE INDEX IF NOT EXISTS idx_ticket_history_environment
ON ticket_history(environment);

-- Composite index for status filtering with created_at sorting
CREATE INDEX IF NOT EXISTS idx_ticket_history_status_created
ON ticket_history(status, created_at DESC);

-- Composite index for assigned tickets (workload queries)
CREATE INDEX IF NOT EXISTS idx_ticket_history_assigned_status
ON ticket_history(assigned_to_id, status);

-- Index for team_level filtering
CREATE INDEX IF NOT EXISTS idx_ticket_history_team_level
ON ticket_history(team_level);

-- Composite index for priority and status filtering
CREATE INDEX IF NOT EXISTS idx_ticket_history_priority_status
ON ticket_history(priority, status);


-- SLA Tracker Performance Indexes
-- --------------------------------

-- Index for updated_at (used in status checks and reporting)
CREATE INDEX IF NOT EXISTS idx_sla_tracker_updated_at
ON sla_tracker(updated_at DESC);

-- Composite index for status and time remaining (dashboard queries)
CREATE INDEX IF NOT EXISTS idx_sla_tracker_status_time
ON sla_tracker(status, time_remaining_minutes);

-- Index for deadline-based queries
CREATE INDEX IF NOT EXISTS idx_sla_tracker_deadline
ON sla_tracker(sla_deadline);

-- Index for paused SLA queries
CREATE INDEX IF NOT EXISTS idx_sla_tracker_paused
ON sla_tracker(paused) WHERE paused = TRUE;


-- Escalation Performance Indexes
-- -------------------------------

-- Index for escalation timestamp (history and reporting)
CREATE INDEX IF NOT EXISTS idx_escalation_escalated_at
ON escalation(escalated_at DESC);

-- Composite index for from/to user queries
CREATE INDEX IF NOT EXISTS idx_escalation_users
ON escalation(from_user_id, to_user_id);

-- Index for ticket escalation history
CREATE INDEX IF NOT EXISTS idx_escalation_ticket
ON escalation(ticket_id, escalated_at DESC);


-- Performance Metrics Indexes
-- ----------------------------

-- Composite index for team member daily metrics
CREATE INDEX IF NOT EXISTS idx_performance_metric_member_date
ON performance_metrics(team_member_id, date DESC);

-- Index for date-based aggregations
CREATE INDEX IF NOT EXISTS idx_performance_metric_date
ON performance_metrics(date DESC);


-- Activities Table Indexes
-- -------------------------

-- Index for recent activities queries
CREATE INDEX IF NOT EXISTS idx_activities_created_at
ON activities(created_at DESC);

-- Index for ticket-specific activities
CREATE INDEX IF NOT EXISTS idx_activities_ticket
ON activities(ticket_id, created_at DESC)
WHERE ticket_id IS NOT NULL;

-- Index for activity type filtering
CREATE INDEX IF NOT EXISTS idx_activities_type
ON activities(activity_type);


-- Team Member Indexes
-- --------------------

-- Composite index for active team members by level
CREATE INDEX IF NOT EXISTS idx_team_members_active_level
ON team_members(active, team_level)
WHERE active = TRUE;

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_team_members_email
ON team_members(email) WHERE active = TRUE;


-- ============================================================================
-- ANALYZE TABLES (Update statistics for query planner)
-- ============================================================================

ANALYZE ticket_history;
ANALYZE sla_tracker;
ANALYZE escalation;
ANALYZE performance_metrics;
ANALYZE activities;
ANALYZE team_members;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check all indexes were created successfully
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('ticket_history', 'sla_tracker', 'escalation', 'performance_metrics', 'activities', 'team_members')
ORDER BY tablename, indexname;

-- Show index usage statistics (run after application has been running for a while)
-- This helps identify which indexes are actually being used
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND tablename IN ('ticket_history', 'sla_tracker', 'escalation', 'performance_metrics', 'activities', 'team_members')
ORDER BY idx_scan DESC;
