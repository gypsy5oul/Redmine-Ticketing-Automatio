/**
 * React Query hooks for Dashboard
 */

import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '../lib/queryClient'
import api from '../services/api'
import type { DashboardMetrics } from '@/types'

/**
 * Fetch dashboard metrics
 * Auto-refreshes every 30 seconds
 */
export function useDashboardMetrics() {
  return useQuery<DashboardMetrics>({
    queryKey: queryKeys.dashboard.metrics(),
    queryFn: async () => api.getDashboardMetrics(),
    staleTime: 1000 * 30, // 30 seconds
    refetchInterval: 1000 * 30, // Auto-refetch every 30 seconds
  })
}

/**
 * Fetch dashboard stats (different from metrics)
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: queryKeys.dashboard.stats(),
    queryFn: async () => {
      // Placeholder - implement when backend endpoint exists
      return {
        totalTickets: 0,
        resolvedToday: 0,
        slaCompliance: 0,
      }
    },
    staleTime: 1000 * 60, // 1 minute
  })
}
