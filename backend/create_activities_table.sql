-- Migration: Create activities table for real-time activity feed
-- Date: 2025-10-30

CREATE TYPE activity_type AS ENUM (
    'ticket_created',
    'ticket_assigned',
    'ticket_updated',
    'ticket_resolved',
    'ticket_escalated',
    'sla_warning',
    'sla_critical',
    'sla_breached',
    'comment_added',
    'collaboration_added',
    'member_added',
    'member_updated'
);

CREATE TABLE IF NOT EXISTS activities (
    id SERIAL PRIMARY KEY,
    activity_type activity_type NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    ticket_id INTEGER REFERENCES ticket_history(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES team_members(id) ON DELETE SET NULL,
    metadata TEXT,
    icon VARCHAR(50),
    color VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_activities_type ON activities(activity_type);
CREATE INDEX idx_activities_ticket_id ON activities(ticket_id);
CREATE INDEX idx_activities_created_at ON activities(created_at DESC);

-- Comment
COMMENT ON TABLE activities IS 'System activity log for real-time feed';
COMMENT ON COLUMN activities.metadata IS 'JSON string for additional activity data';
