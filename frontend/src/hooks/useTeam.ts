/**
 * React Query hooks for Team Management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../lib/queryClient'
import api from '../services/api'
import type { TeamMember, MemberPerformanceSummary } from '../types'

/**
 * Fetch all team members
 */
export function useTeamMembers(level?: string) {
  return useQuery<TeamMember[]>({
    queryKey: [...queryKeys.team.members(), { level: level ?? 'all' }],
    queryFn: async () => api.getTeamMembers(level),
    staleTime: 1000 * 60 * 2, // 2 minutes - team data doesn't change often
  })
}

/**
 * Fetch single team member
 */
export function useTeamMember(memberId: number | null) {
  return useQuery<TeamMember>({
    queryKey: queryKeys.team.member(memberId!),
    queryFn: async () => {
      if (!memberId) throw new Error('Member ID is required')
      const response = await api.getTeamMember(memberId)
      return response
    },
    enabled: !!memberId,
  })
}

/**
 * Fetch team member performance
 */
export function useTeamMemberPerformance(
  memberId: number | null,
  startDate?: string,
  endDate?: string
) {
  return useQuery<MemberPerformanceSummary>({
    queryKey: [
      ...queryKeys.team.performance(memberId ?? 0),
      { startDate, endDate },
    ],
    queryFn: async () => {
      if (!memberId) throw new Error('Member ID is required')
      return api.getTeamMemberPerformance(memberId, {
        start_date: startDate,
        end_date: endDate,
      })
    },
    enabled: !!memberId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Mutation to add a new team member
 */
export function useAddTeamMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (member: Omit<TeamMember, 'id'>) => {
      return api.createTeamMember(member)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.team.members() })
    },
  })
}

/**
 * Mutation to update a team member
 */
export function useUpdateTeamMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      memberId,
      updates,
    }: {
      memberId: number
      updates: Partial<TeamMember>
    }) => {
      return api.updateTeamMember(memberId, updates)
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.team.members() })
      queryClient.invalidateQueries({
        queryKey: queryKeys.team.member(variables.memberId),
      })
    },
  })
}

/**
 * Mutation to delete a team member
 */
export function useDeleteTeamMember() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (memberId: number) => {
      return api.deleteTeamMember(memberId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.team.members() })
    },
  })
}
