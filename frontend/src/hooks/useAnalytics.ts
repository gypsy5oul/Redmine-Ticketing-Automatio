/**
 * React Query hooks for Analytics and ML
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../lib/queryClient'
import api from '../services/api'

/**
 * Fetch ticket volume forecast
 */
export function useForecast(days: number = 7) {
  return useQuery({
    queryKey: queryKeys.analytics.forecast(days),
    queryFn: async () => {
      const response = await api.getTicketVolumeForecast(days)
      return response
    },
    staleTime: 1000 * 60 * 15, // 15 minutes - forecast doesn't change often
  })
}

/**
 * Fetch team performance data
 */
export function useTeamPerformance(startDate?: string, endDate?: string) {
  return useQuery({
    queryKey: queryKeys.analytics.teamPerformance(startDate, endDate),
    queryFn: async () => {
      const response = await api.getTeamPerformance(startDate, endDate)
      return response
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

/**
 * Fetch ML models status
 */
export function useMLModelsStatus() {
  return useQuery({
    queryKey: queryKeys.ml.modelsStatus(),
    queryFn: async () => {
      const response = await api.getMLModelsStatus()
      return response
    },
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

/**
 * Mutation to train ML models
 */
export function useTrainMLModels() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (forceRetrain: boolean = false) => {
      return api.trainMLModels(forceRetrain)
    },
    onSuccess: () => {
      // Refetch models status after training
      queryClient.invalidateQueries({ queryKey: queryKeys.ml.modelsStatus() })
    },
  })
}

/**
 * Predict ticket category using ML
 */
export function usePredictCategory(subject: string, description: string) {
  return useQuery({
    queryKey: queryKeys.ml.prediction('category', { subject, description }),
    queryFn: async () => {
      const response = await api.client.post('/api/v1/ml/predict/category', {
        subject,
        description,
      })
      return response.data
    },
    enabled: subject.length > 0, // Only run if subject is provided
    staleTime: Infinity, // Cache predictions forever (deterministic)
  })
}

/**
 * Predict ticket complexity using ML
 */
export function usePredictComplexity(
  subject: string,
  description: string,
  priority: string = 'P3(Medium)'
) {
  return useQuery({
    queryKey: queryKeys.ml.prediction('complexity', {
      subject,
      description,
      priority,
    }),
    queryFn: async () => {
      const response = await api.client.post('/api/v1/ml/predict/complexity', {
        subject,
        description,
        priority,
      })
      return response.data
    },
    enabled: subject.length > 0,
    staleTime: Infinity,
  })
}

/**
 * Predict all ticket attributes using ML
 */
export function usePredictAll(
  subject: string,
  description: string,
  priority: string = 'P3(Medium)'
) {
  return useQuery({
    queryKey: queryKeys.ml.prediction('all', { subject, description, priority }),
    queryFn: async () => {
      const response = await api.client.post('/api/v1/ml/predict/all', {
        subject,
        description,
        priority,
      })
      return response.data
    },
    enabled: subject.length > 3, // At least 4 characters
    staleTime: Infinity,
  })
}
