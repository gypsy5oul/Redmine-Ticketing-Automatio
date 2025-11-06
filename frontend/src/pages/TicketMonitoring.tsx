import { useState, useEffect, useMemo, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Button,
  CircularProgress,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Snackbar,
  Stack,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  Checkbox,
  FormControlLabel,
  MenuItem,
} from '@mui/material'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import RefreshIcon from '@mui/icons-material/Refresh'
import LaunchIcon from '@mui/icons-material/Launch'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import PauseIcon from '@mui/icons-material/Pause'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import GroupIcon from '@mui/icons-material/Group'
import TableRowsIcon from '@mui/icons-material/TableRows'
import ViewKanbanIcon from '@mui/icons-material/ViewKanban'
import { format } from 'date-fns'
import apiClient from '@/services/api'
import type {
  Ticket,
  SLATracker,
  AdvancedTicketFilters,
  TeamMember,
  TicketQueryFilters,
  WorkSessionType,
  ActiveWorkSession,
} from '@/types'
import TicketDetailDialog from '@/components/TicketDetailDialog'
import TicketFilterPanel from '@/components/TicketFilterPanel'
import KanbanBoard, { type KanbanColumn } from '@/components/KanbanBoard'

interface TicketWithSLA extends Ticket {
  sla_tracker?: SLATracker
}

const createDefaultFilters = (): AdvancedTicketFilters => ({
  statuses: [],
  priorities: [],
  teamLevels: [],
  slaStatuses: [],
  assignedToIds: [],
  categories: [],
  dateFrom: null,
  dateTo: null,
  ticketNumber: '',
})

const arraysEqual = (a: (string | number)[], b: (string | number)[]) => {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false
  }
  return true
}

const filtersEqual = (a: AdvancedTicketFilters, b: AdvancedTicketFilters) =>
  arraysEqual(a.statuses, b.statuses) &&
  arraysEqual(a.priorities, b.priorities) &&
  arraysEqual(a.teamLevels, b.teamLevels) &&
  arraysEqual(a.slaStatuses, b.slaStatuses) &&
  arraysEqual(a.assignedToIds, b.assignedToIds) &&
  arraysEqual(a.categories, b.categories) &&
  a.dateFrom === b.dateFrom &&
  a.dateTo === b.dateTo &&
  a.ticketNumber === b.ticketNumber &&
  a.filterId === b.filterId

const formatDuration = (minutes?: number | null): string => {
  if (!minutes || minutes <= 0) return '0m'
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  if (hours > 0) {
    return `${hours}h ${remainingMinutes}m`
  }
  return `${remainingMinutes}m`
}

const WORK_PAUSE_OPTIONS: { value: WorkSessionType; label: string }[] = [
  { value: 'waiting_customer', label: 'Waiting for customer response' },
  { value: 'waiting_approval', label: 'Waiting for approval' },
  { value: 'waiting_deployment', label: 'Waiting for deployment window' },
  { value: 'waiting_external', label: 'Waiting on external team' },
]

const normalizeFilters = (input: AdvancedTicketFilters): AdvancedTicketFilters => ({
  statuses: [...input.statuses],
  priorities: [...input.priorities],
  teamLevels: [...input.teamLevels],
  slaStatuses: [...input.slaStatuses],
  assignedToIds: [...input.assignedToIds],
  categories: [...input.categories],
  dateFrom: input.dateFrom ?? null,
  dateTo: input.dateTo ?? null,
  ticketNumber: input.ticketNumber ?? '',
  filterId: input.filterId,
})

const toArrayParam = (params: URLSearchParams, key: string) =>
  params
    .getAll(key)
    .flatMap((value) => value.split(','))
    .map((value) => value.trim())
    .filter(Boolean)

const parseQueryToFilters = (search: string): AdvancedTicketFilters => {
  const params = new URLSearchParams(search)
  const statuses = toArrayParam(params, 'status')
  const priorities = toArrayParam(params, 'priority')
  const teamLevels = [...toArrayParam(params, 'team_level'), ...toArrayParam(params, 'team')]
  const slaStatuses = [...toArrayParam(params, 'sla_status'), ...toArrayParam(params, 'sla')]
  const categories = [...toArrayParam(params, 'categories'), ...toArrayParam(params, 'category')]
  const assignedToIds = params
    .getAll('assigned_to_id')
    .map((value) => parseInt(value, 10))
    .filter((value) => Number.isInteger(value))
  const dateFrom = params.get('created_from') || params.get('from')
  const dateTo = params.get('created_to') || params.get('to')
  const ticketNumber = params.get('ticket_number') || params.get('ticket') || ''
  const filterIdParam = params.get('filter_id')

  return normalizeFilters({
    statuses,
    priorities,
    teamLevels,
    slaStatuses,
    assignedToIds,
    categories,
    dateFrom: dateFrom || null,
    dateTo: dateTo || null,
    ticketNumber,
    filterId: filterIdParam ? Number(filterIdParam) : undefined,
  })
}

const filtersToQueryString = (filters: AdvancedTicketFilters): string => {
  const params = new URLSearchParams()

  filters.statuses.forEach((value) => params.append('status', value))
  filters.priorities.forEach((value) => params.append('priority', value))
  filters.teamLevels.forEach((value) => params.append('team_level', value))
  filters.slaStatuses.forEach((value) => params.append('sla_status', value))
  filters.assignedToIds.forEach((value) => params.append('assigned_to_id', String(value)))
  filters.categories.forEach((value) => params.append('categories', value))

  if (filters.dateFrom) params.append('created_from', filters.dateFrom)
  if (filters.dateTo) params.append('created_to', filters.dateTo)
  if (filters.ticketNumber && filters.ticketNumber.trim()) params.append('ticket_number', filters.ticketNumber.trim())
  if (typeof filters.filterId === 'number') params.append('filter_id', String(filters.filterId))

  return params.toString()
}

const toApiFilters = (filters: AdvancedTicketFilters): TicketQueryFilters => ({
  statuses: filters.statuses,
  priorities: filters.priorities,
  team_levels: filters.teamLevels,
  sla_statuses: filters.slaStatuses,
  assigned_to_ids: filters.assignedToIds,
  categories: filters.categories,
  created_from: filters.dateFrom,
  created_to: filters.dateTo,
  ticket_number: filters.ticketNumber,
  filter_id: filters.filterId,
})

interface KanbanColumnConfig {
  id: string
  title: string
  accentColor: string
  statuses: string[]
}

const KANBAN_COLUMN_CONFIG: KanbanColumnConfig[] = [
  {
    id: 'new',
    title: 'New',
    accentColor: '#42a5f5',
    statuses: ['new'],
  },
  {
    id: 'progress',
    title: 'In Progress',
    accentColor: '#7e57c2',
    statuses: ['assigned', 'in_progress', 'escalated', 'reopened'],
  },
  {
    id: 'pending',
    title: 'Pending Customer',
    accentColor: '#ffb74d',
    statuses: ['pending'],
  },
  {
    id: 'resolved',
    title: 'Resolved',
    accentColor: '#66bb6a',
    statuses: ['resolved', 'closed'],
  },
]

export default function TicketMonitoring() {
  const navigate = useNavigate()
  const location = useLocation()
  const [tickets, setTickets] = useState<TicketWithSLA[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<AdvancedTicketFilters>(() => createDefaultFilters())
  const [filtersInitialized, setFiltersInitialized] = useState(false)
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([])
  const [teamMembersLoading, setTeamMembersLoading] = useState(false)
  const [viewMode, setViewMode] = useState<'table' | 'board'>('table')
  const [slaPauseDialogOpen, setSlaPauseDialogOpen] = useState(false)
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [slaPauseReason, setSlaPauseReason] = useState('')
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [selectedTicket, setSelectedTicket] = useState<TicketWithSLA | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [activeWorkSessions, setActiveWorkSessions] = useState<ActiveWorkSession[]>([])
  const [workActionLoading, setWorkActionLoading] = useState(false)
  const [workPauseDialogOpen, setWorkPauseDialogOpen] = useState(false)
  const [workPauseTargetId, setWorkPauseTargetId] = useState<number | null>(null)
  const [workPauseReason, setWorkPauseReason] = useState<WorkSessionType>('waiting_customer')
  const [workPauseNotes, setWorkPauseNotes] = useState('')
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false)
  const [resolveTarget, setResolveTarget] = useState<{ ticketId: number; close: boolean } | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')
  const [resolveCloseTicket, setResolveCloseTicket] = useState(false)

  useEffect(() => {
    const parsedFilters = parseQueryToFilters(location.search)
    setFilters((previous) => {
      if (filtersEqual(previous, parsedFilters)) {
        return previous
      }
      return normalizeFilters(parsedFilters)
    })
    setFiltersInitialized(true)
  }, [location.search])

  useEffect(() => {
    const loadTeamMembers = async () => {
      try {
        setTeamMembersLoading(true)
        const members = await apiClient.getTeamMembers()
        setTeamMembers(members)
      } catch (error) {
        console.error('Failed to load team members', error)
      } finally {
        setTeamMembersLoading(false)
      }
    }

    loadTeamMembers()
  }, [])

  const showSnackbar = useCallback((message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity })
  }, [])

  const loadActiveSessions = useCallback(async () => {
    try {
      const response = await apiClient.getActiveWorkSessions()
      setActiveWorkSessions(response.active_sessions || [])
    } catch (error) {
      console.error('Failed to load active work sessions:', error)
    }
  }, [])

  const fetchTickets = useCallback(async (showSpinner: boolean = true) => {
    if (!filtersInitialized) return
    try {
      if (showSpinner) setLoading(true)
      const apiFilters = toApiFilters(filters)
      const ticketsData = await apiClient.getTickets(apiFilters)

      // SLA tracker data is now included in the tickets response (optimized - no N+1 queries!)
      setTickets(ticketsData)
      setSelectedTicket((current) => {
        if (!current) return current
        const updatedSelection = ticketsData.find((ticket) => ticket.id === current.id)
        return updatedSelection || current
      })
      setLastUpdated(new Date())
      await loadActiveSessions()
    } catch (error) {
      console.error('Failed to fetch tickets:', error)
      showSnackbar('Failed to load tickets', 'error')
    } finally {
      if (showSpinner) setLoading(false)
    }
  }, [filters, filtersInitialized, showSnackbar, loadActiveSessions])

  useEffect(() => {
    if (!filtersInitialized) return undefined

    fetchTickets()

    // Auto-refresh every 30 seconds without UI flicker
    const interval = setInterval(() => {
      fetchTickets(false)
    }, 30000)

    return () => {
      clearInterval(interval)
    }
  }, [fetchTickets, filtersInitialized])

  useEffect(() => {
    loadActiveSessions()
    const interval = setInterval(() => {
      loadActiveSessions()
    }, 30000)
    return () => clearInterval(interval)
  }, [loadActiveSessions])

  useEffect(() => {
    if (resolveTarget) {
      setResolveCloseTicket(resolveTarget.close)
    }
  }, [resolveTarget])

  useEffect(() => {
    if (!filtersInitialized) return

    const nextQuery = filtersToQueryString(filters)
    const currentQuery = location.search.startsWith('?') ? location.search.slice(1) : location.search

    if (nextQuery === currentQuery) return

    navigate({ pathname: location.pathname, search: nextQuery ? `?${nextQuery}` : '' }, { replace: true })
  }, [filters, filtersInitialized, location.pathname, location.search, navigate])

  const handleFiltersChange = (updatedFilters: AdvancedTicketFilters) => {
    setFilters((previous) => {
      if (filtersEqual(previous, updatedFilters)) return previous
      return normalizeFilters(updatedFilters)
    })
  }

  const handleClearFilters = () => {
    setFilters(createDefaultFilters())
  }

  const handleViewModeChange = (_event: React.MouseEvent<HTMLElement>, value: 'table' | 'board' | null) => {
    if (!value) return
    setViewMode(value)
  }

  const handleRefresh = () => {
    fetchTickets()
  }

  const kanbanColumns = useMemo<KanbanColumn[]>(
    () =>
      KANBAN_COLUMN_CONFIG.map((config) => ({
        id: config.id,
        title: config.title,
        accentColor: config.accentColor,
        tickets: tickets.filter((ticket) => config.statuses.includes((ticket.status || '').toString())),
      })),
    [tickets]
  )

  const handleKanbanDrop = async (ticketId: number, targetColumnId: string) => {
    const columnConfig = KANBAN_COLUMN_CONFIG.find((config) => config.id === targetColumnId)
    if (!columnConfig || columnConfig.statuses.length === 0) return

    const targetStatus = columnConfig.statuses[0]

    if (['resolved', 'closed'].includes(targetStatus)) {
      handleResolveRequest(ticketId, targetStatus === 'closed')
      return
    }

    try {
      await apiClient.updateTicket(ticketId, { status: targetStatus })
      showSnackbar(`Ticket moved to ${columnConfig.title}`, 'success')
      setTickets((previous) =>
        previous.map((ticket) =>
          ticket.id === ticketId
            ? {
                ...ticket,
                status: targetStatus,
              }
            : ticket
        )
      )
      await fetchTickets(false)
    } catch (error) {
      console.error('Failed to update ticket status:', error)
      showSnackbar('Failed to update ticket status', 'error')
    }
  }

  const lastUpdatedChipLabel = loading
    ? 'Refreshing…'
    : lastUpdated
    ? `Updated ${format(lastUpdated, 'HH:mm:ss')}`
    : 'Not updated yet'
  const lastUpdatedTooltip = lastUpdated
    ? format(lastUpdated, 'yyyy-MM-dd HH:mm:ss')
    : loading
    ? 'Refreshing ticket data'
    : 'Data not loaded yet'
  const lastUpdatedChipColor: 'default' | 'info' = loading ? 'info' : 'default'
  const canStartMoreWork = activeWorkSessions.length < 2

  const handlePauseSLA = async () => {
    if (!selectedTicketId) return

    try {
      await apiClient.pauseSLA(selectedTicketId, slaPauseReason)
      showSnackbar('SLA paused successfully', 'success')
      setSlaPauseDialogOpen(false)
      setSlaPauseReason('')
      setSelectedTicketId(null)
      fetchTickets()
    } catch (error) {
      console.error('Failed to pause SLA:', error)
      showSnackbar('Failed to pause SLA', 'error')
    }
  }

  const handleResumeSLA = async (ticketId: number) => {
    try {
      await apiClient.resumeSLA(ticketId)
      showSnackbar('SLA resumed successfully', 'success')
      fetchTickets()
    } catch (error) {
      console.error('Failed to resume SLA:', error)
      showSnackbar('Failed to resume SLA', 'error')
    }
  }

  const handleStartWork = async (ticketId: number) => {
    setWorkActionLoading(true)
    try {
      await apiClient.startWorkSession(ticketId)
      showSnackbar('Work session started', 'success')
      await fetchTickets(false)
    } catch (error) {
      console.error('Failed to start work session:', error)
      showSnackbar('Failed to start work session', 'error')
    } finally {
      setWorkActionLoading(false)
    }
  }

  const handleResumeWork = async (ticketId: number) => {
    setWorkActionLoading(true)
    try {
      await apiClient.resumeWorkSession(ticketId)
      showSnackbar('Work session resumed', 'success')
      await fetchTickets(false)
    } catch (error) {
      console.error('Failed to resume work session:', error)
      showSnackbar('Failed to resume work session', 'error')
    } finally {
      setWorkActionLoading(false)
    }
  }

  const handlePauseWorkRequest = (ticketId: number) => {
    setWorkPauseTargetId(ticketId)
    setWorkPauseReason('waiting_customer')
    setWorkPauseNotes('')
    setWorkPauseDialogOpen(true)
  }

  const handlePauseWorkSubmit = async () => {
    if (!workPauseTargetId) return
    setWorkActionLoading(true)
    try {
      await apiClient.pauseWorkSession(workPauseTargetId, workPauseReason, workPauseNotes || undefined)
      showSnackbar('Work session paused', 'success')
      setWorkPauseDialogOpen(false)
      setWorkPauseTargetId(null)
      await fetchTickets(false)
    } catch (error) {
      console.error('Failed to pause work session:', error)
      showSnackbar('Failed to pause work session', 'error')
    } finally {
      setWorkActionLoading(false)
    }
  }

  const handleResolveRequest = (ticketId: number, close: boolean = false) => {
    setResolveTarget({ ticketId, close })
    setResolveNotes('')
    setResolveCloseTicket(close)
    setResolveDialogOpen(true)
  }

  const handleResolveSubmit = async () => {
    if (!resolveTarget) return
    if (!resolveNotes.trim()) {
      showSnackbar('Please add resolution notes before submitting', 'error')
      return
    }

    setWorkActionLoading(true)
    try {
      await apiClient.resolveTicket(resolveTarget.ticketId, {
        resolution_notes: resolveNotes.trim(),
        close_ticket: resolveCloseTicket,
      })
      showSnackbar('Ticket resolved successfully', 'success')
      setResolveDialogOpen(false)
      setResolveTarget(null)
      setResolveNotes('')
      setResolveCloseTicket(false)
      await fetchTickets(false)
    } catch (error) {
      console.error('Failed to resolve ticket:', error)
      showSnackbar('Failed to resolve ticket', 'error')
    } finally {
      setWorkActionLoading(false)
    }
  }

  const handleResolveCancel = () => {
    setResolveDialogOpen(false)
    setResolveTarget(null)
    setResolveNotes('')
    setResolveCloseTicket(false)
  }

  const handleEscalate = async (ticketId: number) => {
    const ticket = tickets.find((t) => t.id === ticketId)
    if (!ticket) return

    const nextLevel = ticket.team_level === 'L1' ? 'L2' : 'L3'
    const confirmed = window.confirm(
      `Escalate ticket #${ticket.redmine_ticket_id} from ${ticket.team_level} to ${nextLevel}?`
    )

    if (!confirmed) return

    try {
      await apiClient.manualEscalate(ticketId, {
        to_team_level: nextLevel,
        reason: 'manual_request',
        notes: 'Manual escalation from admin portal',
      })
      showSnackbar('Ticket escalated successfully', 'success')
      fetchTickets()
    } catch (error) {
      console.error('Failed to escalate ticket:', error)
      showSnackbar('Failed to escalate ticket', 'error')
    }
  }

  const getPriorityColor = (priority: string) => {
    const normalized = (priority || '').toUpperCase()

    if (normalized.includes('P1')) return 'error'
    if (normalized.includes('P2')) return 'warning'
    if (normalized.includes('P3')) return 'info'
    if (normalized.includes('P4')) return 'success'
    if (normalized.includes('P5')) return 'default'

    return 'default'
  }

  const getSLAColor = (status: string | undefined) => {
    switch (status) {
      case 'within_sla':
        return 'success'
      case 'at_risk':
        return 'warning'
      case 'critical':
      case 'breached':
        return 'error'
      case 'paused':
      case 'met':
        return 'default'
      default:
        return 'default'
    }
  }

  const columns: GridColDef[] = [
    {
      field: 'redmine_ticket_id',
      headerName: 'Ticket ID',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Box display="flex" alignItems="center" gap={1}>
          <Typography variant="body2">#{params.value}</Typography>
          <IconButton
            size="small"
            href={params.row.redmine_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <LaunchIcon fontSize="small" />
          </IconButton>
        </Box>
      ),
    },
    {
      field: 'subject',
      headerName: 'Subject',
      flex: 1,
      minWidth: 250,
    },
    {
      field: 'priority',
      headerName: 'Priority',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value} color={getPriorityColor(params.value)} size="small" />
      ),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={(params.value || '').toString().replace('_', ' ').toUpperCase() || 'UNKNOWN'}
          size="small"
          variant="outlined"
        />
      ),
    },
    {
      field: 'assigned_to',
      headerName: 'Assigned To',
      width: 150,
      renderCell: (params: GridRenderCellParams) => params.value?.name || 'Unassigned',
    },
    {
      field: 'requester_name',
      headerName: 'Requester',
      width: 180,
      renderCell: (params: GridRenderCellParams) => (
        <Typography variant="body2" color="text.primary">
          {params.value || 'Customer'}
        </Typography>
      ),
    },
    {
      field: 'work_state',
      headerName: 'Work State',
      width: 240,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => {
        const ticket = params.row as TicketWithSLA
        const activeSession = ticket.active_session
        const statusValue = (ticket.status || '').toString()
        const isTerminal = ['resolved', 'closed'].includes(statusValue)
        const hasActiveWork = activeSession?.type === 'active_work'
        const isWaiting = !!activeSession && !hasActiveWork && activeSession.type !== 'idle'
        const workMinutes = ticket.total_work_minutes ?? 0
        const waitingMinutes = ticket.total_waiting_minutes ?? 0
        const idleMinutes = ticket.total_idle_minutes ?? 0

        const startButton = (
          <Button
            size="small"
            variant="contained"
            onClick={() => handleStartWork(ticket.id)}
            disabled={!canStartMoreWork || workActionLoading || isTerminal}
          >
            Start
          </Button>
        )

        const startButtonWithTooltip = !canStartMoreWork && !isTerminal
          ? (
              <Tooltip title="You already have two active work sessions">
                <span>{startButton}</span>
              </Tooltip>
            )
          : startButton

        return (
          <Box display="flex" flexDirection="column" gap={0.75} width="100%">
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap alignItems="center">
              <Chip label={`Work ${formatDuration(workMinutes)}`} size="small" color="primary" variant="outlined" />
              <Chip label={`Wait ${formatDuration(waitingMinutes)}`} size="small" color="warning" variant="outlined" />
              <Chip label={`Idle ${formatDuration(idleMinutes)}`} size="small" variant="outlined" />
            </Stack>
            {isTerminal ? (
              <Typography variant="caption" color="text.secondary">
                Ticket resolved
              </Typography>
            ) : (
              <Stack direction="row" spacing={0.75} alignItems="center">
                {hasActiveWork && (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => handlePauseWorkRequest(ticket.id)}
                    disabled={workActionLoading}
                  >
                    Pause
                  </Button>
                )}
                {isWaiting && (
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => handleResumeWork(ticket.id)}
                    disabled={workActionLoading}
                  >
                    Resume
                  </Button>
                )}
                {!hasActiveWork && !isWaiting && startButtonWithTooltip}
              </Stack>
            )}
          </Box>
        )
      },
    },
    {
      field: 'team_level',
      headerName: 'Level',
      width: 80,
      renderCell: (params: GridRenderCellParams) => (
        <Chip label={params.value} size="small" color="primary" />
      ),
    },
    {
      field: 'sla_tracker',
      headerName: 'SLA Status',
      width: 200,
      renderCell: (params: GridRenderCellParams) => {
        const sla = params.value as SLATracker | undefined
        if (!sla) return '-'

        const statusLabel = (sla.status || '').replace('_', ' ').toUpperCase() || 'UNKNOWN'
        const timeRemaining =
          typeof sla.time_remaining_minutes === 'number'
            ? `${sla.time_remaining_minutes}m`
            : '—'
        const completion = Math.min(100, Math.max(0, sla.completion_percentage ?? 0))

        return (
          <Box width="100%">
            <Box display="flex" justifyContent="space-between" mb={0.5}>
              <Chip
                label={statusLabel}
                color={getSLAColor(sla.status || 'within_sla')}
                size="small"
              />
              <Typography variant="caption">{timeRemaining}</Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={completion}
              color={
                completion >= 90
                  ? 'error'
                  : completion >= 80
                  ? 'warning'
                  : 'primary'
              }
            />
          </Box>
        )
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 220,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => {
        const statusValue = (params.row.status || '').toString()
        const isTerminal = ['resolved', 'closed'].includes(statusValue)

        return (
          <Box display="flex" gap={0.5} alignItems="center">
            {params.row.sla_tracker?.paused ? (
              <IconButton
                size="small"
                color="success"
                onClick={() => handleResumeSLA(params.row.id)}
                title="Resume SLA"
              >
                <PlayArrowIcon />
              </IconButton>
            ) : (
              <IconButton
                size="small"
                color="warning"
                onClick={() => {
                  setSelectedTicketId(params.row.id)
                  setSlaPauseDialogOpen(true)
                }}
                title="Pause SLA"
              >
                <PauseIcon />
              </IconButton>
            )}
            <IconButton
              size="small"
              color="error"
              onClick={() => handleEscalate(params.row.id)}
              title="Escalate"
              disabled={params.row.team_level === 'L3'}
            >
              <TrendingUpIcon />
            </IconButton>
            <IconButton
              size="small"
              color="primary"
              onClick={() => navigate(`/collaboration/${params.row.id}`)}
              title="Collaboration"
            >
              <GroupIcon />
            </IconButton>
            <Tooltip title={isTerminal ? 'Ticket already resolved' : 'Add resolution notes and resolve'}>
              <span>
                <Button
                  size="small"
                  variant="text"
                  onClick={() => handleResolveRequest(params.row.id)}
                  disabled={isTerminal || workActionLoading}
                >
                  Resolve
                </Button>
              </span>
            </Tooltip>
          </Box>
        )
      },
    },
  ]

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100vh', pb: 4 }}>
      <Box
        sx={{
          bgcolor: 'primary.main',
          color: 'primary.contrastText',
          py: 4,
          px: 3,
          mb: 4,
          borderRadius: 2,
          boxShadow: 3,
        }}
      >
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={2}
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', md: 'center' }}
        >
          <Box>
            <Typography variant="h3" fontWeight={700} gutterBottom>
              Ticket Monitoring
            </Typography>
            <Typography variant="body1" sx={{ opacity: 0.95 }}>
              Advanced filters, saved queries, and Kanban drag-and-drop for rapid triage.
            </Typography>
          </Box>
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <ToggleButtonGroup
              size="small"
              value={viewMode}
              exclusive
              onChange={handleViewModeChange}
              aria-label="ticket view mode"
              sx={{
                bgcolor: 'background.paper',
                '& .MuiToggleButton-root': {
                  color: 'text.primary',
                  '&.Mui-selected': {
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                  },
                },
              }}
            >
              <ToggleButton value="table" aria-label="table view">
                <TableRowsIcon fontSize="small" />
              </ToggleButton>
              <ToggleButton value="board" aria-label="kanban view">
                <ViewKanbanIcon fontSize="small" />
              </ToggleButton>
            </ToggleButtonGroup>
            <Tooltip title={lastUpdatedTooltip} placement="bottom">
              <Chip
                label={lastUpdatedChipLabel}
                size="medium"
                variant="filled"
                color={lastUpdatedChipColor}
                sx={{
                  bgcolor: 'background.paper',
                  color: 'text.primary',
                  fontWeight: 600,
                }}
              />
            </Tooltip>
            <Tooltip title="Refresh tickets">
              <span>
                <Button
                  variant="contained"
                  startIcon={<RefreshIcon />}
                  onClick={handleRefresh}
                  disabled={loading}
                  sx={{
                    bgcolor: 'background.paper',
                    color: 'primary.main',
                    '&:hover': {
                      bgcolor: 'grey.200',
                    },
                  }}
                >
                  Refresh
                </Button>
              </span>
            </Tooltip>
          </Stack>
        </Stack>
      </Box>

      <Box sx={{ px: 3 }}>
        <Card sx={{ mb: 4, boxShadow: 2, borderRadius: 3 }}>
          <CardContent sx={{ p: 3 }}>
            <Stack spacing={2.5}>
              <Stack direction="row" alignItems="center" justifyContent="space-between">
                <Typography variant="h5" fontWeight={600}>
                  Active Work Sessions
                </Typography>
                <Chip
                  label={`${activeWorkSessions.length}/2 active`}
                  size="medium"
                  color={canStartMoreWork ? 'success' : 'warning'}
                  sx={{ fontWeight: 600 }}
                />
              </Stack>
              {activeWorkSessions.length === 0 ? (
                <Box
                  sx={{
                    p: 3,
                    borderRadius: 2,
                    bgcolor: 'grey.50',
                    border: '1px dashed',
                    borderColor: 'grey.300',
                    textAlign: 'center',
                  }}
                >
                  <Typography variant="body1" color="text.secondary">
                    No active work sessions. Select a ticket and click &quot;Start Work&quot; to begin tracking focused time.
                  </Typography>
                </Box>
              ) : (
                activeWorkSessions.map((session) => {
                const matchingTicket = tickets.find((t) => t.id === session.ticket_id)
                const subject = matchingTicket?.subject || session.ticket_subject || 'Active ticket'
                const redmineId = matchingTicket?.redmine_ticket_id || session.ticket_redmine_id
                const requester = matchingTicket?.requester_name || 'Customer'
                return (
                  <Card
                    key={session.session_id}
                    elevation={0}
                    sx={{
                      border: '2px solid',
                      borderColor: 'primary.main',
                      borderRadius: 2,
                      bgcolor: 'primary.50',
                      transition: 'all 0.2s',
                      '&:hover': {
                        boxShadow: 3,
                        transform: 'translateY(-2px)',
                      },
                    }}
                  >
                    <CardContent sx={{ p: 2.5 }}>
                      <Stack
                        direction={{ xs: 'column', md: 'row' }}
                        spacing={2}
                        alignItems={{ xs: 'flex-start', md: 'center' }}
                        justifyContent="space-between"
                      >
                        <Box flex={1}>
                          <Typography variant="h6" fontWeight={600} gutterBottom>
                            #{redmineId} · {subject}
                          </Typography>
                          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                            <Chip
                              label={`Active for ${formatDuration(session.duration_minutes)}`}
                              size="small"
                              color="primary"
                              sx={{ fontWeight: 600 }}
                            />
                            {matchingTicket?.work_efficiency_percent !== undefined && matchingTicket.work_efficiency_percent !== null && (
                              <Chip
                                label={`Efficiency ${Math.round(matchingTicket.work_efficiency_percent)}%`}
                                size="small"
                                color="success"
                                variant="outlined"
                              />
                            )}
                            <Chip label={`Raised by ${requester}`} size="small" variant="outlined" />
                          </Stack>
                        </Box>
                        <Stack direction="row" spacing={1.5}>
                          <Button
                            size="medium"
                            variant="outlined"
                            color="warning"
                            onClick={() => handlePauseWorkRequest(session.ticket_id)}
                            disabled={workActionLoading}
                          >
                            Pause
                          </Button>
                          <Button
                            size="medium"
                            variant="contained"
                            onClick={() => {
                              if (matchingTicket) {
                                setSelectedTicket(matchingTicket)
                                setDetailDialogOpen(true)
                              }
                            }}
                          >
                            Details
                          </Button>
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                )
              })
            )}
          </Stack>
        </CardContent>
      </Card>

        <TicketFilterPanel
          filters={filters}
          onFiltersChange={handleFiltersChange}
          onClear={handleClearFilters}
          teamMembers={teamMembers}
          loadingMembers={teamMembersLoading}
        />

        <Card sx={{ boxShadow: 2, borderRadius: 3 }}>
          <CardContent sx={{ p: 3 }}>
            {loading ? (
              <Box display="flex" justifyContent="center" p={6}>
                <CircularProgress size={60} />
              </Box>
            ) : viewMode === 'board' ? (
            <KanbanBoard
              columns={kanbanColumns}
              onCardDrop={handleKanbanDrop}
              onStartWork={handleStartWork}
              onResumeWork={handleResumeWork}
              onPauseWork={handlePauseWorkRequest}
              workActionLoading={workActionLoading}
              canStartMoreWork={canStartMoreWork}
            />
          ) : (
            <DataGrid
              rows={tickets}
              columns={columns}
              initialState={{
                pagination: {
                  paginationModel: { page: 0, pageSize: 25 },
                },
              }}
              pageSizeOptions={[10, 25, 50, 100]}
              onRowClick={(params) => {
                setSelectedTicket(params.row as TicketWithSLA)
                setDetailDialogOpen(true)
              }}
              sx={{
                '& .MuiDataGrid-row': {
                  cursor: 'pointer',
                  '&:hover': {
                    bgcolor: 'action.hover',
                  },
                },
              }}
              autoHeight
              getRowHeight={() => 70}
            />
          )}
        </CardContent>
      </Card>
      </Box>

      {/* Pause SLA Dialog */}
      <Dialog open={slaPauseDialogOpen} onClose={() => setSlaPauseDialogOpen(false)}>
        <DialogTitle>Pause SLA Tracking</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Reason for pausing"
            value={slaPauseReason}
            onChange={(e) => setSlaPauseReason(e.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSlaPauseDialogOpen(false)}>Cancel</Button>
          <Button onClick={handlePauseSLA} variant="contained" disabled={!slaPauseReason}>
            Pause SLA
          </Button>
        </DialogActions>
      </Dialog>

      {/* Pause Work Session Dialog */}
      <Dialog open={workPauseDialogOpen} onClose={() => setWorkPauseDialogOpen(false)}>
        <DialogTitle>Pause Work Session</DialogTitle>
        <DialogContent sx={{ minWidth: { xs: 280, sm: 360 } }}>
          <TextField
            select
            fullWidth
            label="Pause reason"
            value={workPauseReason}
            onChange={(event) => setWorkPauseReason(event.target.value as WorkSessionType)}
            sx={{ mt: 1 }}
          >
            {WORK_PAUSE_OPTIONS.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Notes (optional)"
            value={workPauseNotes}
            onChange={(event) => setWorkPauseNotes(event.target.value)}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWorkPauseDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handlePauseWorkSubmit}
            variant="contained"
            disabled={!workPauseTargetId || workActionLoading}
          >
            Pause Work
          </Button>
        </DialogActions>
      </Dialog>

      {/* Resolve Ticket Dialog */}
      <Dialog open={resolveDialogOpen} onClose={handleResolveCancel} fullWidth maxWidth="sm">
        <DialogTitle>Resolve Ticket</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            Provide detailed resolution notes so the team and Redmine stay in sync.
          </Typography>
          <TextField
            fullWidth
            multiline
            rows={4}
            label="Resolution notes"
            value={resolveNotes}
            onChange={(event) => setResolveNotes(event.target.value)}
            sx={{ mt: 2 }}
            placeholder="Explain the fix, rollbacks, follow-up tasks, or customer updates."
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={resolveCloseTicket}
                onChange={(event) => setResolveCloseTicket(event.target.checked)}
              />
            }
            label="Also mark this ticket as fully closed"
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleResolveCancel}>Cancel</Button>
          <Button
            onClick={handleResolveSubmit}
            variant="contained"
            disabled={!resolveNotes.trim() || workActionLoading}
          >
            Submit Resolution
          </Button>
        </DialogActions>
      </Dialog>

      {/* Ticket Detail Dialog */}
      <TicketDetailDialog
        open={detailDialogOpen}
        ticket={selectedTicket}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedTicket(null)
        }}
        onStartWork={handleStartWork}
        onResumeWork={handleResumeWork}
        onPauseWork={handlePauseWorkRequest}
        workActionLoading={workActionLoading}
        canStartMoreWork={canStartMoreWork}
        onResolveTicket={handleResolveRequest}
      />

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}
