import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  TeamLevel,
  TeamMember,
  Skill,
  Ticket,
  SLAPolicy,
  SLATracker,
  SLAStatus,
  Escalation,
  CollaborationSummary,
  DashboardMetrics,
  WorkloadSummary,
  TicketVolumeData,
  TeamPerformanceData,
  TicketComment,
  CommentListResponse,
  TicketQueryFilters,
  MLModelsStatusResponse,
  MLTrainingResult,
  ShiftAssignment,
  MemberLeave,
  LeaveStatusEnum,
  WorkSessionSummary,
  ActiveWorkSession,
  WorkActionResponse,
  WorkSessionType,
  ProjectSummaryListResponse,
  ProjectDetailResponse,
} from '@/types';
import { CommentType } from '@/types';

// Use relative URL since Nginx will proxy /api/ requests to backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class APIClient {
  public client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });

    // Request interceptor for adding auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          // Unauthorized - clear tokens and redirect to login
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Generic HTTP methods
  async get<T = any>(url: string, config?: any) {
    const response = await this.client.get<T>(url.startsWith('/api') ? url : `/api/v1${url}`, config);
    return response;
  }

  async post<T = any>(url: string, data?: any, config?: any) {
    const response = await this.client.post<T>(url.startsWith('/api') ? url : `/api/v1${url}`, data, config);
    return response;
  }

  // Health Check
  async healthCheck() {
    const response = await this.client.get('/health');
    return response.data;
  }

  // Team Management APIs
  async getTeamMembers(level?: string) {
    const params = level ? { team_level: level, active_only: true } : { active_only: true };
    const response = await this.client.get<{members: TeamMember[], success: boolean, count: number}>('/api/v1/team/members', { params });
    return response.data.members.map((member) => ({
      ...member,
      team_level: member.team_level as TeamLevel,
    }));
  }

  async getTeamMember(id: number) {
    const response = await this.client.get<{member: TeamMember}>(`/api/v1/team/members/${id}`);
    return {
      ...response.data.member,
      team_level: response.data.member.team_level as TeamLevel,
    };
  }

  async createTeamMember(data: Partial<TeamMember>) {
    const response = await this.client.post<{success: boolean, member: TeamMember}>('/api/v1/team/members', data);
    return {
      ...response.data.member,
      team_level: response.data.member.team_level as TeamLevel,
    };
  }

  async updateTeamMember(id: number, data: Partial<TeamMember>) {
    const response = await this.client.put<{success: boolean, member: TeamMember}>(`/api/v1/team/members/${id}`, data);
    return {
      ...response.data.member,
      team_level: response.data.member.team_level as TeamLevel,
    };
  }

  async deleteTeamMember(id: number) {
    const response = await this.client.delete(`/api/v1/team/members/${id}`);
    return response.data;
  }

  async getTeamMemberPerformance(memberId: number, params?: { start_date?: string; end_date?: string }) {
    const response = await this.client.get(`/api/v1/team/members/${memberId}/performance`, {
      params,
    });
    return response.data;
  }

  async getSkills() {
    const response = await this.client.get<{skills: Skill[], total: number}>('/api/v1/team/skills');
    return response.data.skills;
  }

  async createSkill(data: Partial<Skill>) {
    const response = await this.client.post<{success: boolean, skill: Skill}>('/api/v1/team/skills', data);
    return response.data.skill;
  }

  // Ticket APIs
  async getTickets(filters?: TicketQueryFilters) {
    const priorityMap: Record<string, string> = {
      P1: 'P1(Critical)',
      P2: 'P2(High)',
      P3: 'P3(Medium)',
      P4: 'P4(Low)',
      P5: 'P5(Trivial)',
    }

    const params = new URLSearchParams();
    const appendAll = (key: string, values?: Array<string | number>) => {
      if (!values || values.length === 0) return;
      values.forEach((value) => {
        params.append(key, String(value));
      });
    };

    if (filters) {
      appendAll('status', filters.statuses);

      if (filters.priorities?.length) {
        const mapped = filters.priorities.map((priority) => priorityMap[priority] || priority);
        appendAll('priority', mapped);
      }

      appendAll('team_level', filters.team_levels);
      appendAll('sla_status', filters.sla_statuses);
      appendAll('assigned_to_id', filters.assigned_to_ids);
      appendAll('categories', filters.categories);
      appendAll('category', filters.categories);

      if (filters.created_from) {
        params.append('created_from', filters.created_from);
      }
      if (filters.created_to) {
        params.append('created_to', filters.created_to);
      }
      if (filters.ticket_number && filters.ticket_number.trim()) {
        params.append('ticket_number', filters.ticket_number.trim());
      }
      if (typeof filters.filter_id === 'number') {
        params.append('filter_id', String(filters.filter_id));
      }
    }

    const queryString = params.toString();
    const response = await this.client.get<{tickets: Ticket[], total: number}>(
      `/api/v1/tickets${queryString ? `?${queryString}` : ''}`
    );
    return response.data.tickets.map((ticket) => ({
      ...ticket,
      team_level: ticket.team_level as TeamLevel,
      status: ticket.status,
      requester_name: ticket.requester_name ?? null,
      resolution_notes: ticket.resolution_notes ?? null,
      total_work_minutes: ticket.total_work_minutes ?? 0,
      total_waiting_minutes: ticket.total_waiting_minutes ?? 0,
      total_idle_minutes: ticket.total_idle_minutes ?? 0,
      work_efficiency_percent: ticket.work_efficiency_percent ?? null,
      last_work_session_at: ticket.last_work_session_at ?? null,
      active_session: ticket.active_session ?? null,
    }));
  }

  async getTicket(id: number) {
    const response = await this.client.get<Ticket>(`/api/v1/tickets/${id}`);
    return {
      ...response.data,
      team_level: response.data.team_level as TeamLevel,
      status: response.data.status,
      requester_name: response.data.requester_name ?? null,
      resolution_notes: response.data.resolution_notes ?? null,
      total_work_minutes: response.data.total_work_minutes ?? 0,
      total_waiting_minutes: response.data.total_waiting_minutes ?? 0,
      total_idle_minutes: response.data.total_idle_minutes ?? 0,
      work_efficiency_percent: response.data.work_efficiency_percent ?? null,
      last_work_session_at: response.data.last_work_session_at ?? null,
      active_session: response.data.active_session ?? null,
      work_summary: response.data.work_summary as WorkSessionSummary | undefined,
    };
  }

  async startWorkSession(ticketId: number) {
    const response = await this.client.post<WorkActionResponse>(`/api/v1/tickets/${ticketId}/work/start`);
    return response.data;
  }

  async pauseWorkSession(ticketId: number, reason: WorkSessionType, notes?: string) {
    const response = await this.client.post(`/api/v1/tickets/${ticketId}/work/pause`, {
      reason,
      notes,
    });
    return response.data;
  }

  async resumeWorkSession(ticketId: number) {
    const response = await this.client.post(`/api/v1/tickets/${ticketId}/work/resume`);
    return response.data;
  }

  async getWorkSummary(ticketId: number) {
    const response = await this.client.get<WorkSessionSummary>(`/api/v1/tickets/${ticketId}/work/summary`);
    return response.data;
  }

  async getActiveWorkSessions() {
    const response = await this.client.get<{ active_sessions: ActiveWorkSession[]; member_id?: number }>(
      '/api/v1/work/active'
    );
    return response.data;
  }

  async resolveTicket(ticketId: number, data: { resolution_notes: string; close_ticket?: boolean }) {
    const response = await this.client.post<{ success: boolean; ticket: Ticket }>(
      `/api/v1/tickets/${ticketId}/resolve`,
      data
    );
    return response.data;
  }

  async trainMLModels(forceRetrain: boolean = false) {
    const response = await this.client.post<MLTrainingResult>('/api/v1/ml/train', null, {
      params: forceRetrain ? { force_retrain: true } : undefined,
    });
    return response.data;
  }

  async getMLModelsStatus() {
    const response = await this.client.get<MLModelsStatusResponse>('/api/v1/ml/models/status');
    return response.data;
  }

  async processTickets() {
    const response = await this.client.post('/api/v1/tickets/process');
    return response.data;
  }

  async updateTicket(id: number, data: Partial<Ticket>) {
    const response = await this.client.put<Ticket>(`/api/v1/tickets/${id}`, data);
    return response.data;
  }

  // SLA APIs
  async getSLAPolicies() {
    const response = await this.client.get<{policies: SLAPolicy[], total: number}>('/api/v1/sla/policies');
    return response.data.policies || [];
  }

  async updateSLAPolicy(id: number, data: Partial<SLAPolicy>) {
    const response = await this.client.put<{success: boolean; policy: SLAPolicy}>(`/api/v1/sla/policies/${id}`, data);
    return response.data.policy;
  }

  async getSLAStatus(ticketId: number) {
    const response = await this.client.get<SLATracker>(`/api/v1/sla/status/${ticketId}`);
    return {
      ...response.data,
      status: response.data.status as SLAStatus,
    };
  }

  async getAtRiskTickets() {
    const response = await this.client.get<{tickets: any[], count: number}>('/api/v1/sla/at-risk');
    return response.data.tickets.map((tracker) => ({
      ...tracker,
      status: (tracker.status || 'within_sla') as SLAStatus,
      ticket: tracker.ticket,
    }));
  }

  async pauseSLA(ticketId: number, reason?: string) {
    const response = await this.client.post(`/api/v1/sla/${ticketId}/pause`, { reason });
    return response.data;
  }

  async resumeSLA(ticketId: number) {
    const response = await this.client.post(`/api/v1/sla/${ticketId}/resume`);
    return response.data;
  }

  // Workload APIs
  async getWorkload(level?: string) {
    const params = level ? { level } : {};
    const response = await this.client.get<{workload: WorkloadSummary[], count: number}>('/api/v1/workload', { params });
    return response.data.workload.map((w) => ({
      ...w,
      team_level: w.team_level as TeamLevel,
    }));
  }

  async getCapacitySummary() {
    const response = await this.client.get('/api/v1/workload/capacity');
    return response.data;
  }

  async getCapacityAlerts() {
    const response = await this.client.get('/api/v1/workload/alerts');
    return response.data;
  }

  // Escalation APIs
  async manualEscalate(ticketId: number, data: {
    to_team_level: string;
    to_member_id?: number;
    reason: string;
    notes?: string;
  }) {
    const response = await this.client.post<Escalation>(
      `/api/v1/escalation/${ticketId}/manual`,
      data
    );
    return response.data;
  }

  async checkEscalationNeeded(ticketId: number) {
    const response = await this.client.get(`/api/v1/escalation/${ticketId}/check`);
    return response.data;
  }

  async getEscalationHistory(ticketId: number) {
    const response = await this.client.get<{ticket_id: number; escalations?: Escalation[]}>(`/api/v1/escalation/${ticketId}/history`);
    if (Array.isArray((response.data as unknown) as Escalation[])) {
      return response.data as unknown as Escalation[];
    }
    return response.data.escalations ?? [];
  }

  // Collaboration APIs
  async addCollaborator(ticketId: number, data: {
    member_id: number;
    role?: string;
  }) {
    const response = await this.client.post<{success: boolean, collaboration_id: number}>(
      `/api/v1/collaboration/${ticketId}/add`,
      {
        team_member_id: data.member_id,  // Map member_id to team_member_id
        role: data.role || 'secondary'
      }
    );
    return response.data;
  }

  async removeCollaborator(ticketId: number, memberId: number) {
    const response = await this.client.delete(
      `/api/v1/collaboration/${ticketId}/remove/${memberId}`  // Already uses correct path param
    );
    return response.data;
  }

  async getCollaborationSummary(ticketId: number) {
    const response = await this.client.get<CollaborationSummary>(`/api/v1/collaboration/${ticketId}`);
    return response.data;
  }

  // Analytics APIs
  async getTicketVolumeForecast(days: number = 7) {
    const response = await this.client.get<{
      historical?: TicketVolumeData[];
      forecast?: TicketVolumeData[];
      busy_periods?: any[];
      recommendations?: any;
    }>('/api/v1/analytics/forecast', {
      params: { days },
    });

    const historical = (response.data.historical || []).map((item) => ({
      ...item,
      predicted: false,
    }));

    const forecast = (response.data.forecast || []).map((item) => ({
      ...item,
      predicted: true,
    }));

    return [...historical, ...forecast];
  }

  async getSLAPrediction(ticketId: number) {
    const response = await this.client.get(`/api/v1/analytics/sla-prediction/${ticketId}`);
    return response.data;
  }

  async getTeamPerformance(startDate?: string, endDate?: string) {
    const response = await this.client.get<{performance: TeamPerformanceData[], start_date: string, end_date: string}>('/api/v1/analytics/team-performance', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data.performance.map((perf) => ({
      ...perf,
      team_level: perf.team_level as TeamLevel,
    }));
  }

  // Project analytics APIs
  async getProjectSummaries() {
    const response = await this.client.get<ProjectSummaryListResponse>('/api/v1/projects');
    return response.data;
  }

  async getProjectDetail(projectJiraId: string) {
    const response = await this.client.get<ProjectDetailResponse>(`/api/v1/projects/${encodeURIComponent(projectJiraId)}`);
    return response.data;
  }

  // Scheduling APIs
  async getShiftAssignments(params?: { team_level?: string; member_id?: number; include_inactive?: boolean; grouped?: boolean }) {
    if (params?.grouped) {
      const response = await this.client.get<{ count: number; grouped_shifts: any[] }>('/api/v1/shifts', { params });
      return response.data.grouped_shifts;
    }
    const response = await this.client.get<{ count: number; shifts: ShiftAssignment[] }>('/api/v1/shifts', { params });
    return response.data.shifts;
  }

  async createShiftAssignment(payload: Partial<ShiftAssignment> & { team_member_id: number; start_hour: number; end_hour: number }) {
    const response = await this.client.post<{ shift: ShiftAssignment }>('/api/v1/shifts', payload);
    return response.data.shift;
  }

  async updateShiftAssignment(id: number, payload: Partial<ShiftAssignment>) {
    const response = await this.client.put<{ shift: ShiftAssignment }>(`/api/v1/shifts/${id}`, payload);
    return response.data.shift;
  }

  async deleteShiftAssignment(id: number) {
    await this.client.delete(`/api/v1/shifts/${id}`);
  }

  async getLeaves(params?: { team_level?: string; status?: string; include_past?: boolean }) {
    const response = await this.client.get<{ count: number; leaves: MemberLeave[] }>('/api/v1/leaves', { params });
    return response.data.leaves;
  }

  async getMyLeaves(includePast: boolean = true) {
    const response = await this.client.get<{ count: number; leaves: MemberLeave[] }>('/api/v1/leaves/me', {
      params: { include_past: includePast },
    });
    return response.data.leaves;
  }

  async createLeave(payload: { start_date: string; end_date: string; leave_type?: string; reason?: string; team_member_id?: number }) {
    const response = await this.client.post<{ leave: MemberLeave }>('/api/v1/leaves', payload);
    return response.data.leave;
  }

  async updateLeave(id: number, payload: Partial<MemberLeave>) {
    const response = await this.client.put<{ leave: MemberLeave }>(`/api/v1/leaves/${id}`, payload);
    return response.data.leave;
  }

  async deleteLeave(id: number) {
    await this.client.delete(`/api/v1/leaves/${id}`);
  }

  async updateLeaveStatus(id: number, status: LeaveStatusEnum) {
    const response = await this.client.post<{ leave: MemberLeave }>(`/api/v1/leaves/${id}/status`, { status });
    return response.data.leave;
  }

  // On-call scheduling APIs
  async getOncallAssignments(weekStart?: string) {
    const response = await this.client.get<{ assignments: any[]; count: number }>('/api/v1/oncall/assignments', {
      params: weekStart ? { week_start: weekStart } : undefined,
    });
    return response.data.assignments;
  }

  async runOncallAssignments(weekStart?: string, force: boolean = false) {
    const response = await this.client.post<{ assignments: any[] }>('/api/v1/oncall/assignments/run', {
      week_start: weekStart,
      force,
    });
    return response.data.assignments;
  }

  async rotateOncall(teamLevel: string, weekStart: string) {
    const response = await this.client.get<{ assignment: any }>('/api/v1/oncall/rotate', {
      params: { team_level: teamLevel, week_start: weekStart },
    });
    return response.data.assignment;
  }

  async replaceOncallAssignment(assignmentId: number, newMemberId: number, reason?: string) {
    const payload: Record<string, any> = {
      team_member_id: newMemberId,
    };
    if (reason) {
      payload.reason = reason;
    }
    const response = await this.client.post<{ assignment: any }>(`/api/v1/oncall/assignments/${assignmentId}/replace`, payload);
    return response.data.assignment;
  }

  // Dashboard APIs
  async getDashboardMetrics() {
    const response = await this.client.get<DashboardMetrics>('/api/v1/dashboard/metrics');
    return response.data;
  }

  async getRecentActivity(limit: number = 20) {
    const response = await this.client.get('/api/v1/dashboard/activity', { params: { limit } });
    return response.data;
  }

  // Scheduler APIs
  async getSchedulerStatus() {
    const response = await this.client.get('/api/v1/scheduler/status');
    return response.data;
  }

  // Comment APIs
  async getTicketComments(ticketId: number, commentType?: CommentType) {
    const params = commentType ? { comment_type: commentType } : {};
    const response = await this.client.get<CommentListResponse>(`/api/v1/tickets/${ticketId}/comments`, { params });
    return response.data;
  }

  async createComment(ticketId: number, content: string, authorId: number, commentType: CommentType = CommentType.PUBLIC) {
    const params = new URLSearchParams({
      content,
      author_id: authorId.toString(),
      comment_type: commentType,
    });
    const response = await this.client.post<{success: boolean, comment: TicketComment}>(`/api/v1/tickets/${ticketId}/comments?${params.toString()}`);
    return response.data.comment;
  }

  async updateComment(commentId: number, content: string) {
    const params = new URLSearchParams({ content });
    const response = await this.client.put<{success: boolean, comment: Partial<TicketComment>}>(`/api/v1/comments/${commentId}?${params.toString()}`);
    return response.data.comment;
  }

  async deleteComment(commentId: number) {
    const response = await this.client.delete<{success: boolean, message: string, comment_id: number, ticket_id: number}>(`/api/v1/comments/${commentId}`);
    return response.data;
  }

  // Activity APIs
  async getActivities(limit: number = 50, hours: number = 24) {
    // Backend currently returns recent ticket updates from /dashboard/activity
    const response = await this.client.get<{ activities?: any[] }>('/api/v1/dashboard/activity', {
      params: { limit, hours },
    });

    const activities = response.data?.activities ?? [];
    return {
      success: true,
      activities,
    };
  }

  async getTicketActivities(ticketId: number, limit: number = 20) {
    const response = await this.client.get(`/api/v1/activities/ticket/${ticketId}`, { params: { limit } });
    return response.data;
  }
}

export const apiClient = new APIClient();
export default apiClient;
