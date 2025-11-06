/**
 * React Query hooks for Tickets
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../lib/queryClient'
import api from '../services/api'
import type {
  Ticket,
  TicketQueryFilters,
  CommentListResponse,
  TicketComment,
} from '../types'
import { CommentType } from '../types'

type ResolveTicketVariables = {
  ticketId: number
  resolution: string
  closeTicket?: boolean
}

type AddCommentVariables = {
  ticketId: number
  content: string
  authorId: number
  authorName?: string
  commentType?: CommentType
}

type AddCommentContext = {
  previousComments?: CommentListResponse
}

/**
 * Fetch all tickets with optional filters
 */
export function useTickets(
  filters?: TicketQueryFilters,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: queryKeys.tickets.list(filters as Record<string, unknown>),
    queryFn: async () => {
      const response = await api.getTickets(filters)
      return response
    },
    staleTime: 1000 * 30, // 30 seconds - tickets change frequently
    enabled: options?.enabled ?? true,
  })
}

/**
 * Fetch single ticket by ID
 */
export function useTicket(ticketId: number | null) {
  return useQuery({
    queryKey: queryKeys.tickets.detail(ticketId!),
    queryFn: async () => {
      if (!ticketId) throw new Error('Ticket ID is required')
      const response = await api.getTicket(ticketId)
      return response
    },
    enabled: !!ticketId, // Only run if ticketId exists
  })
}

/**
 * Fetch ticket comments
 */
export function useTicketComments(ticketId: number | null) {
  return useQuery({
    queryKey: queryKeys.tickets.comments(ticketId!),
    queryFn: async () => {
      if (!ticketId) throw new Error('Ticket ID is required')
      const response = await api.getTicketComments(ticketId)
      return response
    },
    enabled: !!ticketId,
    staleTime: 1000 * 15, // 15 seconds
  })
}

/**
 * Mutation to resolve a ticket
 */
export function useResolveTicket() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      ticketId,
      resolution,
      closeTicket,
    }: ResolveTicketVariables) => {
      const payload: { resolution_notes: string; close_ticket?: boolean } = {
        resolution_notes: resolution,
      }

      if (typeof closeTicket === 'boolean') {
        payload.close_ticket = closeTicket
      }

      return api.resolveTicket(ticketId, payload)
    },
    onSuccess: (_, variables) => {
      // Invalidate and refetch tickets list
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.lists() })
      // Invalidate specific ticket detail
      queryClient.invalidateQueries({
        queryKey: queryKeys.tickets.detail(variables.ticketId),
      })
      // Invalidate dashboard metrics (ticket counts changed)
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.metrics() })
    },
  })
}

/**
 * Mutation to add a comment to a ticket
 */
export function useAddComment() {
  const queryClient = useQueryClient()

  return useMutation<TicketComment, Error, AddCommentVariables, AddCommentContext>({
    mutationFn: async ({
      ticketId,
      content,
      authorId,
      commentType,
    }: AddCommentVariables) => {
      return api.createComment(
        ticketId,
        content,
        authorId,
        commentType ?? CommentType.PUBLIC
      )
    },
    onMutate: async (variables: AddCommentVariables) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({
        queryKey: queryKeys.tickets.comments(variables.ticketId),
      })

      // Snapshot the previous value
      const previousComments = queryClient.getQueryData<CommentListResponse>(
        queryKeys.tickets.comments(variables.ticketId)
      )

      // Optimistically update to the new value
      queryClient.setQueryData<CommentListResponse>(
        queryKeys.tickets.comments(variables.ticketId),
        (old: CommentListResponse | undefined) => {
          if (!old) return old

          const optimisticComment: TicketComment = {
            id: Date.now(),
            ticket_id: variables.ticketId,
            author_id: variables.authorId,
            author_name: variables.authorName ?? 'You',
            content: variables.content,
            comment_type: variables.commentType ?? CommentType.PUBLIC,
            created_at: new Date().toISOString(),
            updated_at: null,
            edited: false,
            has_attachments: false,
            attachment_count: 0,
          }

          return {
            ...old,
            comments: [...old.comments, optimisticComment],
            total: old.total + 1,
          }
        }
      )

      // Return context with previous value
      return { previousComments }
    },
    onError: (_error, variables, context) => {
      // Rollback on error
      if (context?.previousComments) {
        queryClient.setQueryData<CommentListResponse | undefined>(
          queryKeys.tickets.comments(variables.ticketId),
          context.previousComments
        )
      }
    },
    onSettled: (_result, _error, variables) => {
      if (variables) {
        // Always refetch after error or success
        queryClient.invalidateQueries({
          queryKey: queryKeys.tickets.comments(variables.ticketId),
        })
      }
    },
  })
}

/**
 * Mutation to update a ticket
 */
export function useUpdateTicket() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      ticketId,
      updates,
    }: {
      ticketId: number
      updates: Partial<Ticket>
    }) => {
      return api.updateTicket(ticketId, updates)
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.lists() })
      queryClient.invalidateQueries({
        queryKey: queryKeys.tickets.detail(variables.ticketId),
      })
    },
  })
}

/**
 * Process new tickets (manual trigger)
 */
export function useProcessTickets() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      return api.processTickets()
    },
    onSuccess: () => {
      // Refetch all tickets data
      queryClient.invalidateQueries({ queryKey: queryKeys.tickets.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.metrics() })
    },
  })
}
