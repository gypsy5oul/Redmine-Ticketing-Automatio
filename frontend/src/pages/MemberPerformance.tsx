import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  Alert,
  Chip,
  Button,
  Paper,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material'
import {
  ArrowBack,
  TrendingUp,
  Assignment,
  CheckCircle,
  AccessTime,
  Speed,
  Warning,
  Work as WorkIcon,
} from '@mui/icons-material'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { useTeamMemberPerformance } from '@/hooks/useTeam'
import { useTickets } from '@/hooks/useTickets'
import type { MemberPerformanceSummary } from '@/types'
import WorkEfficiencyChart from '@/components/WorkEfficiencyChart'

export default function MemberPerformance() {
  const { memberId } = useParams<{ memberId: string }>()
  const navigate = useNavigate()
  const parsedMemberId = memberId ? Number(memberId) : NaN
  const memberIdNumber = Number.isFinite(parsedMemberId) ? parsedMemberId : null

  const {
    data: performanceData,
    isLoading: performanceLoading,
    error: performanceError,
  } = useTeamMemberPerformance(memberIdNumber)

  const {
    data: memberTickets = [],
    isLoading: ticketsLoading,
    error: ticketsError,
  } = useTickets(
    memberIdNumber ? { assigned_to_ids: [memberIdNumber] } : undefined,
    { enabled: !!memberIdNumber }
  )

  const isLoading = performanceLoading || ticketsLoading
  const combinedError = performanceError ?? ticketsError
  const errorMessage = combinedError
    ? combinedError instanceof Error
      ? combinedError.message
      : (combinedError as any)?.response?.data?.detail ?? 'Failed to load performance data'
    : ''
  const data: MemberPerformanceSummary | null = performanceData ?? null

  if (!memberIdNumber) {
    return (
      <Box p={3}>
        <Alert severity="error">Invalid team member identifier.</Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/team')} sx={{ mt: 2 }}>
          Back to Team Management
        </Button>
      </Box>
    )
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    )
  }

  if (errorMessage) {
    return (
      <Box p={3}>
        <Alert severity="error">{errorMessage}</Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/team')} sx={{ mt: 2 }}>
          Back to Team Management
        </Button>
      </Box>
    )
  }

  if (!data) {
    return (
      <Box p={3}>
        <Alert severity="warning">No performance data available</Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/team')} sx={{ mt: 2 }}>
          Back to Team Management
        </Button>
      </Box>
    )
  }

  const { member, performance, recent_tickets, workload_trend } = data

  const getCapacityColor = (percentage: number) => {
    if (percentage >= 90) return 'error'
    if (percentage >= 70) return 'warning'
    return 'success'
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'error'> = {
      OPEN: 'primary',
      IN_PROGRESS: 'warning',
      RESOLVED: 'success',
      CLOSED: 'default',
      ON_HOLD: 'error',
    }
    return colors[status] || 'default'
  }

  return (
    <Box>
      {/* Header */}
      <Box mb={3} display="flex" justifyContent="space-between" alignItems="center">
        <Box>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/team')}
            sx={{ mb: 1 }}
          >
            Back to Team Management
          </Button>
          <Typography variant="h4" fontWeight="bold">
            {member.name}
          </Typography>
          <Box display="flex" gap={1} mt={1}>
            <Chip label={member.team_level} color="primary" size="small" />
            <Chip label={member.email} variant="outlined" size="small" />
            <Chip
              label={member.active ? 'Active' : 'Inactive'}
              color={member.active ? 'success' : 'default'}
              size="small"
            />
          </Box>
        </Box>
      </Box>

      {/* Key Metrics Cards */}
      <Grid container spacing={3} mb={3}>
        {/* Current Workload */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Assignment color="primary" sx={{ mr: 1 }} />
                <Typography variant="subtitle2" color="text.secondary">
                  Current Workload
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="bold">
                {member.current_tickets} / {member.max_tickets}
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min(member.capacity_percentage, 100)}
                color={getCapacityColor(member.capacity_percentage)}
                sx={{ mt: 1, mb: 0.5 }}
              />
              <Typography variant="caption" color="text.secondary">
                {member.capacity_percentage.toFixed(1)}% Capacity
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* SLA Compliance */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <Speed color="success" sx={{ mr: 1 }} />
                <Typography variant="subtitle2" color="text.secondary">
                  SLA Compliance
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="bold">
                {performance.sla_compliance_rate.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {performance.tickets_breached} breached tickets
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Avg Resolution Time */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <AccessTime color="info" sx={{ mr: 1 }} />
                <Typography variant="subtitle2" color="text.secondary">
                  Avg Resolution Time
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="bold">
                {performance.avg_resolution_time_hours.toFixed(1)}h
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {performance.tickets_resolved + performance.tickets_closed} completed
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Total Tickets */}
        <Grid item xs={12} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={1}>
                <TrendingUp color="warning" sx={{ mr: 1 }} />
                <Typography variant="subtitle2" color="text.secondary">
                  Total Assigned
                </Typography>
              </Box>
              <Typography variant="h4" fontWeight="bold">
                {performance.total_tickets_assigned}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {performance.active_collaborations} collaborations
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Ticket Status Breakdown */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Ticket Status Breakdown
              </Typography>
              <Grid container spacing={2} mt={1}>
                <Grid item xs={6}>
                  <Box textAlign="center" p={2} bgcolor="primary.50" borderRadius={2}>
                    <Typography variant="h3" color="primary.main" fontWeight="bold">
                      {performance.tickets_open}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Open
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center" p={2} bgcolor="warning.50" borderRadius={2}>
                    <Typography variant="h3" color="warning.main" fontWeight="bold">
                      {performance.tickets_in_progress}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      In Progress
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center" p={2} bgcolor="success.50" borderRadius={2}>
                    <Typography variant="h3" color="success.main" fontWeight="bold">
                      {performance.tickets_resolved}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Resolved
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6}>
                  <Box textAlign="center" p={2} bgcolor="grey.100" borderRadius={2}>
                    <Typography variant="h3" color="text.secondary" fontWeight="bold">
                      {performance.tickets_closed}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Closed
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Workload Trend Chart */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Workload Trend (Last 30 Days)
              </Typography>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={workload_trend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => {
                      const date = new Date(value)
                      return `${date.getMonth() + 1}/${date.getDate()}`
                    }}
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(value) => new Date(value).toLocaleDateString()}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="active_tickets"
                    stroke="#1976d2"
                    strokeWidth={2}
                    name="Active Tickets"
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Work Efficiency */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <WorkIcon color="primary" sx={{ mr: 1 }} />
                <Typography variant="h6" fontWeight="bold">
                  Work Efficiency Metrics
                </Typography>
              </Box>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <WorkEfficiencyChart
                    totalWorkMinutes={memberTickets.reduce((sum, t) => sum + (t.total_work_minutes || 0), 0)}
                    totalWaitingMinutes={memberTickets.reduce((sum, t) => sum + (t.total_waiting_minutes || 0), 0)}
                    totalIdleMinutes={memberTickets.reduce((sum, t) => sum + (t.total_idle_minutes || 0), 0)}
                    workEfficiencyPercent={
                      memberTickets.filter((t) => (t.total_work_minutes || 0) > 0).length > 0
                        ? memberTickets
                            .filter((t) => (t.total_work_minutes || 0) > 0)
                            .reduce((sum, t) => sum + (t.work_efficiency_percent || 0), 0) /
                          memberTickets.filter((t) => (t.total_work_minutes || 0) > 0).length
                        : 0
                    }
                    variant="full"
                    showLegend={true}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <Grid container spacing={2}>
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          Total Active Work
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="primary.main">
                          {Math.round(memberTickets.reduce((sum, t) => sum + (t.total_work_minutes || 0), 0) / 60)}h
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          Waiting Time
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="warning.main">
                          {Math.round(memberTickets.reduce((sum, t) => sum + (t.total_waiting_minutes || 0), 0) / 60)}h
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          Idle Time
                        </Typography>
                        <Typography variant="h5" fontWeight={700}>
                          {Math.round(memberTickets.reduce((sum, t) => sum + (t.total_idle_minutes || 0), 0) / 60)}h
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6}>
                      <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                        <Typography variant="caption" color="text.secondary">
                          Tickets with Work
                        </Typography>
                        <Typography variant="h5" fontWeight={700} color="success.main">
                          {memberTickets.filter((t) => (t.total_work_minutes || 0) > 0).length}
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Tickets */}
      <Card>
        <CardContent>
          <Typography variant="h6" fontWeight="bold" gutterBottom>
            Recent Tickets
          </Typography>
          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Ticket ID</TableCell>
                  <TableCell>Subject</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Priority</TableCell>
                  <TableCell>SLA</TableCell>
                  <TableCell>Updated</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {recent_tickets.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography color="text.secondary">No tickets found</Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  recent_tickets.map((ticket) => (
                    <TableRow key={ticket.id} hover>
                      <TableCell>#{ticket.redmine_ticket_id}</TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 300 }}>
                          {ticket.subject}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={ticket.status}
                          color={getStatusColor(ticket.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip label={ticket.priority} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        {ticket.sla_breached ? (
                          <Chip
                            icon={<Warning />}
                            label="Breached"
                            color="error"
                            size="small"
                          />
                        ) : (
                          <Chip
                            icon={<CheckCircle />}
                            label="OK"
                            color="success"
                            size="small"
                          />
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {new Date(ticket.updated_at).toLocaleString()}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Box>
  )
}
