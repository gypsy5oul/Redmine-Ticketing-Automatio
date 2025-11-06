// Team Types
export enum TeamLevel {
  L1 = 'L1',
  L2 = 'L2',
  L3 = 'L3',
}

export interface Skill {
  id: number;
  name: string;
  category: string;
  description?: string;
}

export interface TeamMember {
  id: number;
  redmine_user_id: number;
  user_id?: number | null;
  name: string;
  email: string;
  team_level: TeamLevel;
  max_tickets: number;
  current_tickets?: number;
  timezone: string;
  work_start_hour: number;
  work_end_hour: number;
  active: boolean;
  skills: Skill[];
  total_tickets_resolved: number; // Fixed: was total_tickets_assigned
  avg_resolution_time_hours: number;
  sla_compliance_rate: number;
}

// Ticket Types
export enum TicketPriority {
  P1_CRITICAL = 'P1(Critical)',
  P2_HIGH = 'P2(High)',
  P3_MEDIUM = 'P3(Medium)',
  P4_LOW = 'P4(Low)',
  P5_TRIVIAL = 'P5(Trivial)',
}

export enum TicketStatus {
  NEW = 'new',
  ASSIGNED = 'assigned',
  IN_PROGRESS = 'in_progress',
  RESOLVED = 'resolved',
  CLOSED = 'closed',
  ESCALATED = 'escalated',
}

export type WorkSessionType =
  | 'active_work'
  | 'waiting_customer'
  | 'waiting_approval'
  | 'waiting_deployment'
  | 'waiting_external'
  | 'idle';

export interface WorkSession {
  id: number;
  type: WorkSessionType;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number;
  is_active: boolean;
  notes?: string | null;
  paused_reason?: string | null;
}

export interface WorkSessionSummary {
  ticket_id: number;
  redmine_ticket_id?: number;
  work_started_at?: string | null;
  total_work_minutes: number;
  total_waiting_minutes: number;
  total_idle_minutes: number;
  work_efficiency_percent?: number | null;
  work_sessions: WorkSession[];
  active_session?: WorkSession | null;
}

export interface ActiveWorkSession {
  session_id: number;
  ticket_id: number;
  ticket_redmine_id?: number | null;
  ticket_subject?: string | null;
  started_at?: string | null;
  duration_minutes: number;
  is_running: boolean;
}

export interface WorkActionResponse {
  success: boolean;
  ticket_id: number;
  session_id: number;
  ticket_status: string;
  active_sessions_count: number;
  can_accept_more_work: boolean;
  started_at?: string | null;
}

export interface TicketAssignee {
  id: number;
  name: string;
}

export interface TicketAttachment {
  id: number;
  filename: string;
  filesize: number;
  content_url: string;
  content_type: string;
  description?: string;
  created_on: string;
}

export interface Ticket {
  id: number;
  redmine_ticket_id: number;
  subject: string;
  description?: string;
  attachments?: TicketAttachment[];
  priority: TicketPriority | string;
  status: TicketStatus | string;
  environment?: string;
  assigned_to_id?: number;
  assigned_to?: TicketAssignee | null;
  team_level: TeamLevel;
  category?: string;
  complexity?: string;
  estimated_resolution_hours?: number;
  created_at?: string;
  updated_at?: string;
  assigned_at?: string;
  redmine_url?: string;
  requester_name?: string | null;
  resolution_notes?: string | null;
  last_work_session_at?: string | null;
  total_work_minutes?: number;
  total_waiting_minutes?: number;
  total_idle_minutes?: number;
  work_efficiency_percent?: number | null;
  active_session?: {
    id: number;
    type: WorkSessionType;
    team_member_id: number;
    started_at: string | null;
  } | null;
  work_summary?: WorkSessionSummary;
}

export interface TicketQueryFilters {
  statuses?: string[];
  priorities?: string[];
  team_levels?: string[];
  sla_statuses?: string[];
  assigned_to_ids?: number[];
  categories?: string[];
  created_from?: string | null;
  created_to?: string | null;
  ticket_number?: string;
  filter_id?: number;
}

export interface AdvancedTicketFilters {
  statuses: string[];
  priorities: string[];
  teamLevels: string[];
  slaStatuses: string[];
  assignedToIds: number[];
  categories: string[];
  dateFrom: string | null;
  dateTo: string | null;
  ticketNumber?: string;
  filterId?: number;
}

export interface SavedTicketFilterPayload {
  id: string;
  name: string;
  description?: string;
  filters: TicketQueryFilters;
  created_at: string;
}

export interface MLModelStatus {
  exists: boolean;
  last_modified?: string;
  size_kb?: number;
}

export interface MLModelsStatusResponse {
  models: Record<string, MLModelStatus>;
  models_path: string;
  all_present: boolean;
}

export interface MLTrainingResult {
  success: boolean;
  error?: string;
  training_samples?: number;
  models_trained?: number;
  trained_at?: string;
  results?: Record<string, unknown>;
  current_count?: number;
}

// Scheduling Types
export interface ShiftAssignment {
  id: number;
  team_member_id: number;
  team_member_name: string | null;
  team_level: TeamLevel | string | null;
  day_of_week: number | null;
  start_hour: number;
  start_minute: number;
  end_hour: number;
  end_minute: number;
  timezone: string;
  effective_from: string | null;
  effective_to: string | null;
  priority: number;
  is_active: boolean;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export enum LeaveStatusEnum {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  CANCELLED = 'cancelled',
}

export enum LeaveTypeEnum {
  VACATION = 'vacation',
  SICK = 'sick',
  TRAINING = 'training',
  UNPLANNED = 'unplanned',
  OTHER = 'other',
}

export interface MemberLeave {
  id: number;
  team_member_id: number;
  team_member_name: string | null;
  team_level: TeamLevel | string | null;
  start_date: string;
  end_date: string;
  leave_type: LeaveTypeEnum | string;
  status: LeaveStatusEnum | string;
  reason?: string | null;
  created_by?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

// SLA Types
export enum SLAStatus {
  WITHIN_SLA = 'within_sla',
  AT_RISK = 'at_risk',
  CRITICAL = 'critical',
  BREACHED = 'breached',
  PAUSED = 'paused',
  MET = 'met',
}

export interface SLAPolicy {
  id: number;
  priority: string;
  response_time_minutes: number;
  resolution_time_minutes: number;
  escalation_time_minutes: number;
  business_hours_only: boolean;
  environment?: string;
  active: boolean;
}

export interface SLATracker {
  id: number;
  status: SLAStatus;
  ticket?: Ticket;
  ticket_id?: number;
  policy_id?: number;
  policy?: SLAPolicy;
  response_deadline?: string;
  resolution_deadline?: string;
  response_completed_at?: string;
  resolution_completed_at?: string;
  paused?: boolean;
  total_paused_minutes?: number;
  time_remaining_minutes?: number;
  completion_percentage?: number;
}

// Escalation Types
export enum EscalationReason {
  SLA_DEADLINE = 'sla_deadline',
  NO_RESPONSE = 'no_response',
  COMPLEXITY = 'complexity',
  MANUAL_REQUEST = 'manual_request',
}

export interface Escalation {
  id: number;
  ticket_id: number;
  from_team_level: TeamLevel;
  to_team_level: TeamLevel;
  from_member_id?: number;
  to_member_id?: number;
  reason: EscalationReason;
  notes?: string;
  escalated_at: string;
  acknowledged_at?: string;
}

// Collaboration Types
export interface Collaboration {
  id: number;
  ticket_id: number;
  team_member_id: number;
  team_member: TeamMember;
  role: string;
  contribution_percentage?: number;
  joined_at: string;
  left_at?: string;
  is_active: boolean;
}

export interface CollaborationSummary {
  ticket_id: number;
  is_collaborative: boolean;
  active_collaborators: number;
  past_collaborators: number;
  total_collaborators: number;
  collaborators: Collaboration[];
  total_time_spent_hours: number;
  total_comments: number;
  primary_assignee?: {
    id: number;
    name: string;
  } | null;
}

// Analytics Types
export interface TicketVolumeData {
  date: string;
  count: number;
  predicted?: boolean;
  lower_bound?: number;
  upper_bound?: number;
  confidence?: number;
}

export interface SLAComplianceData {
  period: string;
  compliance_rate: number;
  total_tickets: number;
  breached_tickets: number;
}

export interface TeamPerformanceData {
  member_id: number;
  member_name: string;
  team_level: TeamLevel;
  tickets_resolved: number;
  avg_resolution_time: number;
  sla_compliance_rate: number;
}

export interface MemberPerformanceSummary {
  success: boolean;
  member: {
    id: number;
    name: string;
    email: string;
    team_level: string;
    active: boolean;
    current_tickets: number;
    max_tickets: number;
    capacity_percentage: number;
  };
  performance: {
    total_tickets_assigned: number;
    tickets_open: number;
    tickets_in_progress: number;
    tickets_resolved: number;
    tickets_closed: number;
    tickets_on_hold: number;
    tickets_breached: number;
    sla_compliance_rate: number;
    avg_resolution_time_hours: number;
    active_collaborations: number;
  };
  recent_tickets: Array<{
    id: number;
    redmine_ticket_id: number;
    subject: string;
    status: string;
    priority: string;
    sla_breached: boolean;
    created_at: string;
    updated_at: string;
  }>;
  workload_trend: Array<{
    date: string;
    active_tickets: number;
  }>;
}

// Dashboard Types
export interface DashboardMetrics {
  total_tickets_today: number;
  tickets_in_progress: number;
  sla_compliance_rate: number;
  avg_resolution_time_hours: number;
  at_risk_tickets: number;
  critical_tickets: number;
  team_capacity_percentage: number;
  active_collaborations: number;
  card_insights?: DashboardInsights;
}

export interface SparklinePoint {
  label: string;
  value: number;
}

export interface DistributionDatum {
  label: string;
  value: number;
}

export interface DashboardCardInsight {
  sparkline: SparklinePoint[];
  distribution?: DistributionDatum[];
}

export interface DashboardInsights {
  total_tickets: DashboardCardInsight;
  sla_compliance: DashboardCardInsight;
  at_risk: DashboardCardInsight;
  team_capacity: DashboardCardInsight;
}

// Workload Types
export interface WorkloadSummary {
  member_id: number;
  member_name: string;
  team_level: TeamLevel;
  current_tickets: number;
  max_tickets: number;
  capacity_percentage: number;
  is_available: boolean;
}

// Project Analytics Types
export interface ProjectSummary {
  project_jira_id: string;
  total_tickets: number;
  open_tickets: number;
  resolved_tickets: number;
  breached_tickets: number;
  sla_compliance_rate: number;
  active_engineers: number;
  last_activity?: string | null;
}

export interface ProjectStatusBreakdown {
  status: string;
  count: number;
}

export interface ProjectPriorityBreakdown {
  priority: string;
  count: number;
}

export interface ProjectTeamContributor {
  member_id: number;
  name: string;
  email?: string | null;
  total_tickets: number;
  resolved_tickets: number;
  sla_compliance_rate: number;
}

export interface ProjectRecentTicket {
  ticket_id: number;
  redmine_ticket_id: number;
  subject: string;
  status: string;
  priority: string;
  assigned_to?: string | null;
  sla_breached: boolean;
  created_at: string;
  resolved_at?: string | null;
}

export interface ProjectDetail {
  summary: ProjectSummary;
  status_breakdown: ProjectStatusBreakdown[];
  priority_breakdown: ProjectPriorityBreakdown[];
  team_contributors: ProjectTeamContributor[];
  recent_tickets: ProjectRecentTicket[];
  trend?: ProjectTrendPoint[];
  ai_insights?: string | null;
}

export interface ProjectSummaryListResponse {
  projects: ProjectSummary[];
  count: number;
}

export interface ProjectDetailResponse {
  project: ProjectDetail;
}

export interface ProjectTrendPoint {
  date: string;
  created: number;
  resolved: number;
  breached: number;
  sla_compliance_rate: number;
}

// API Response Types
export interface APIResponse<T> {
  data: T;
  message?: string;
  success: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Comment Types
export enum CommentType {
  PUBLIC = 'public',
  INTERNAL = 'internal',
}

export interface TicketComment {
  id: number;
  ticket_id: number;
  author_id: number | null;
  author_name: string | null;
  content: string;
  comment_type: CommentType | string;
  created_at: string;
  updated_at: string | null;
  edited: boolean;
  has_attachments: boolean;
  attachment_count: number;
}

export interface CommentListResponse {
  comments: TicketComment[];
  total: number;
  ticket_id: number;
}
