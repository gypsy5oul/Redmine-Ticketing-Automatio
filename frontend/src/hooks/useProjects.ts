/**
 * React Query hooks for project analytics.
 */

import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '../lib/queryClient'
import api from '../services/api'
import type {
  ProjectDetailResponse,
  ProjectSummaryListResponse,
} from '@/types'

export function useProjectSummaries() {
  return useQuery<ProjectSummaryListResponse>({
    queryKey: queryKeys.projects.list(),
    queryFn: async () => api.getProjectSummaries(),
    staleTime: 1000 * 60, // 1 minute
  })
}

export function useProjectDetail(projectJiraId: string | null) {
  return useQuery<ProjectDetailResponse>({
    queryKey: queryKeys.projects.detail(projectJiraId ?? ''),
    queryFn: async () => {
      if (!projectJiraId) throw new Error('Project Jira ID is required')
      return api.getProjectDetail(projectJiraId)
    },
    enabled: Boolean(projectJiraId),
    staleTime: 1000 * 60, // 1 minute
  })
}
