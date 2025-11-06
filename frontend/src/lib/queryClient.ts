/**
 * React Query (TanStack Query) Configuration
 *
 * Provides centralized configuration for all data fetching in the application
 */

import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: How long data is considered fresh
      staleTime: 1000 * 60 * 5, // 5 minutes

      // Cache time: How long unused data stays in cache
      gcTime: 1000 * 60 * 10, // 10 minutes (formerly cacheTime)

      // Retry configuration
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

      // Refetch configuration
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      refetchOnMount: true,

      // Error handling
      throwOnError: false,
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
      retryDelay: 1000,
    },
  },
})

/**
 * Query Keys Factory
 * Centralized query key management for consistency
 */
export const queryKeys = {
  // Tickets
  tickets: {
    all: ['tickets'] as const,
    lists: () => [...queryKeys.tickets.all, 'list'] as const,
    list: (filters?: Record<string, unknown>) =>
      [...queryKeys.tickets.lists(), { filters }] as const,
    details: () => [...queryKeys.tickets.all, 'detail'] as const,
    detail: (id: number) => [...queryKeys.tickets.details(), id] as const,
    comments: (ticketId: number) =>
      [...queryKeys.tickets.detail(ticketId), 'comments'] as const,
  },

  // Dashboard
  dashboard: {
    all: ['dashboard'] as const,
    metrics: () => [...queryKeys.dashboard.all, 'metrics'] as const,
    stats: () => [...queryKeys.dashboard.all, 'stats'] as const,
  },

  // Team
  team: {
    all: ['team'] as const,
    members: () => [...queryKeys.team.all, 'members'] as const,
    member: (id: number) => [...queryKeys.team.members(), id] as const,
    performance: (id: number) => [...queryKeys.team.member(id), 'performance'] as const,
    skills: () => [...queryKeys.team.all, 'skills'] as const,
  },

  // SLA
  sla: {
    all: ['sla'] as const,
    policies: () => [...queryKeys.sla.all, 'policies'] as const,
    status: (ticketId: number) => [...queryKeys.sla.all, 'status', ticketId] as const,
    atRisk: () => [...queryKeys.sla.all, 'at-risk'] as const,
  },

  // Analytics
  analytics: {
    all: ['analytics'] as const,
    forecast: (days?: number) =>
      [...queryKeys.analytics.all, 'forecast', days] as const,
    teamPerformance: (startDate?: string, endDate?: string) =>
      [...queryKeys.analytics.all, 'team-performance', { startDate, endDate }] as const,
  },

  // ML
  ml: {
    all: ['ml'] as const,
    modelsStatus: () => [...queryKeys.ml.all, 'models-status'] as const,
    prediction: (type: string, data: Record<string, unknown>) =>
      [...queryKeys.ml.all, 'prediction', type, data] as const,
  },

  // Workload
  workload: {
    all: ['workload'] as const,
    current: () => [...queryKeys.workload.all, 'current'] as const,
    capacity: () => [...queryKeys.workload.all, 'capacity'] as const,
    alerts: () => [...queryKeys.workload.all, 'alerts'] as const,
  },

  // Work Sessions
  workSessions: {
    all: ['workSessions'] as const,
    active: () => [...queryKeys.workSessions.all, 'active'] as const,
  },

  // Projects
  projects: {
    all: ['projects'] as const,
    list: () => [...queryKeys.projects.all, 'list'] as const,
    detail: (projectJiraId: string) =>
      [...queryKeys.projects.all, 'detail', projectJiraId] as const,
  },

  // Scheduling
  scheduling: {
    all: ['scheduling'] as const,
    shifts: () => [...queryKeys.scheduling.all, 'shifts'] as const,
    oncall: () => [...queryKeys.scheduling.all, 'oncall'] as const,
  },
} as const
