import { useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  Breadcrumbs,
  Link,
  Card,
  CardContent,
  Stack,
  Chip,
  Grid,
  CircularProgress,
  Alert,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Paper,
  LinearProgress,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import type { ProjectRecentTicket } from '@/types'
import { useProjectDetail } from '@/hooks/useProjects'
import { formatDistanceToNow } from 'date-fns'
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Legend,
  Tooltip as RechartsTooltip,
} from 'recharts'

const chartColors = ['#5b8def', '#ffaf38', '#66bb6a', '#ef5350', '#7e57c2']

const SLAChip = ({ rate }: { rate: number }) => {
  let color: 'success' | 'warning' | 'error' = 'success'
  if (rate < 85) color = 'error'
  else if (rate < 95) color = 'warning'

  return (
    <Chip
      label={`SLA ${rate.toFixed(1)}%`}
      color={color}
      size="small"
      icon={<CheckCircleIcon fontSize="small" />}
    />
  )
}

const RecentTicketRow = ({ ticket }: { ticket: ProjectRecentTicket }) => {
  const createdLabel = formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })
  const resolvedLabel = ticket.resolved_at
    ? formatDistanceToNow(new Date(ticket.resolved_at), { addSuffix: true })
    : '—'

  return (
    <TableRow hover>
      <TableCell>#{ticket.redmine_ticket_id}</TableCell>
      <TableCell>{ticket.subject}</TableCell>
      <TableCell>{ticket.status}</TableCell>
      <TableCell>{ticket.priority}</TableCell>
      <TableCell>{ticket.assigned_to ?? 'Unassigned'}</TableCell>
      <TableCell>
        <Chip
          size="small"
          label={ticket.sla_breached ? 'Breached' : 'On track'}
          color={ticket.sla_breached ? 'error' : 'success'}
        />
      </TableCell>
      <TableCell>{createdLabel}</TableCell>
      <TableCell>{resolvedLabel}</TableCell>
    </TableRow>
  )
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const {
    data,
    isLoading,
    error,
  } = useProjectDetail(projectId ?? null)

  const project = data?.project
  const summary = project?.summary
  const statusBreakdown = project?.status_breakdown ?? []
  const priorityBreakdown = project?.priority_breakdown ?? []
  const teamContributors = project?.team_contributors ?? []
  const recentTickets = project?.recent_tickets ?? []
  const rawTrend = project?.trend ?? []
  const rawInsights = project?.ai_insights ?? null

  const statusChartData = useMemo(
    () =>
      statusBreakdown.map((row) => ({
        name: row.status,
        value: row.count,
      })),
    [statusBreakdown]
  )

  const priorityChartData = useMemo(
    () =>
      priorityBreakdown.map((row) => ({
        name: row.priority,
        value: row.count,
      })),
    [priorityBreakdown]
  )

  const trendChartData = useMemo(
    () =>
      rawTrend.map((point) => ({
        date: new Date(point.date).toLocaleDateString(),
        created: point.created,
        resolved: point.resolved,
        breached: point.breached,
        compliance: point.sla_compliance_rate,
      })),
    [rawTrend]
  )

  const aiInsights = rawInsights?.trim() || null

  if (!projectId) {
    return (
      <Box p={3}>
        <Alert severity="warning">Project identifier missing.</Alert>
      </Box>
    )
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    )
  }

  if (error || !project || !summary) {
    return (
      <Box p={3}>
        <Alert severity="error">Failed to load project details.</Alert>
      </Box>
    )
  }
  const lastActivityLabel = summary.last_activity
    ? formatDistanceToNow(new Date(summary.last_activity), { addSuffix: true })
    : 'N/A'

  return (
    <Box>
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link component="button" onClick={() => navigate('/projects')} color="inherit">
          <ArrowBackIcon fontSize="small" sx={{ mr: 0.5 }} /> Projects
        </Link>
        <Typography color="text.primary">{summary.project_jira_id}</Typography>
      </Breadcrumbs>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <Stack spacing={2}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h5" fontWeight={700}>
                    {summary.project_jira_id}
                  </Typography>
                  <SLAChip rate={summary.sla_compliance_rate} />
                </Stack>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
                  <Chip
                    label={`${summary.open_tickets} open`}
                    color={summary.open_tickets > 0 ? 'warning' : 'success'}
                    icon={<WarningAmberIcon fontSize="small" />}
                  />
                  <Chip
                    label={`${summary.resolved_tickets} resolved`}
                    variant="outlined"
                  />
                  <Chip
                    label={`${summary.breached_tickets} breached`}
                    color={summary.breached_tickets > 0 ? 'error' : 'success'}
                    icon={<WarningAmberIcon fontSize="small" />}
                  />
                </Stack>
                <Box>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(Math.max(summary.sla_compliance_rate, 0), 100)}
                    sx={{
                      height: 8,
                      borderRadius: 4,
                      '& .MuiLinearProgress-bar': {
                        borderRadius: 4,
                      },
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    SLA compliance trajectory
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  Last activity {lastActivityLabel}
                </Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card
            variant="outlined"
            sx={{
              height: '100%',
              background: 'linear-gradient(135deg, #5b8def22 0%, #5b8def05 100%)',
            }}
          >
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Team Overview
              </Typography>
              <Typography variant="h3" fontWeight={700}>
                {summary.active_engineers}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Active engineers contributing within the last 30 days
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={8}>
          <Card variant="outlined" sx={{ height: 360 }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                30-day trend
              </Typography>
              {trendChartData.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  Insufficient data to display trends.
                </Typography>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendChartData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                    <defs>
                      <linearGradient id="colorCreated" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#5b8def" stopOpacity={0.6} />
                        <stop offset="95%" stopColor="#5b8def" stopOpacity={0.05} />
                      </linearGradient>
                      <linearGradient id="colorResolved" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#66bb6a" stopOpacity={0.6} />
                        <stop offset="95%" stopColor="#66bb6a" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" minTickGap={20} />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" hide domain={[0, 100]} />
                    <RechartsTooltip />
                    <Legend />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="created"
                      stroke="#5b8def"
                      fill="url(#colorCreated)"
                      name="Created"
                    />
                    <Area
                      yAxisId="left"
                      type="monotone"
                      dataKey="resolved"
                      stroke="#66bb6a"
                      fill="url(#colorResolved)"
                      name="Resolved"
                    />
                    <Area
                      yAxisId="right"
                      type="monotone"
                      dataKey="compliance"
                      stroke="#ffa726"
                      fillOpacity={0}
                      name="SLA %"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card variant="outlined" sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                AI Insights
              </Typography>
              {!aiInsights ? (
                <Typography variant="body2" color="text.secondary">
                  Insights will appear here once enough data is available.
                </Typography>
              ) : (
                <Stack spacing={1.2}>
                  {aiInsights
                    .split('\n')
                    .filter((line) => line.trim().length > 0)
                    .map((line, index) => (
                      <Typography variant="body2" key={`${line}-${index}`}>
                        {line}
                      </Typography>
                    ))}
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2, height: 320 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Status distribution
            </Typography>
            {statusChartData.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No tickets available.
              </Typography>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={statusChartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={4}
                  >
                    {statusChartData.map((entry, index) => (
                      <Cell
                        key={`status-slice-${entry.name}`}
                        fill={chartColors[index % chartColors.length]}
                      />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper variant="outlined" sx={{ p: 2, height: 320 }}>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Priority distribution
            </Typography>
            {priorityChartData.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No priority data yet.
              </Typography>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={priorityChartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={4}
                  >
                    {priorityChartData.map((entry, index) => (
                      <Cell
                        key={`priority-slice-${entry.name}`}
                        fill={chartColors[(index + 2) % chartColors.length]}
                      />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Paper>
        </Grid>
      </Grid>

      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Top contributors
              </Typography>
              <Stack spacing={1.5}>
                {teamContributors.length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    No engineering activity recorded yet.
                  </Typography>
                )}
                {teamContributors.map((member) => (
                  <Box key={member.member_id} sx={{ borderBottom: '1px solid', borderColor: 'divider', pb: 1.5 }}>
                    <Typography variant="body2" fontWeight={600}>
                      {member.name}
                    </Typography>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Typography variant="caption" color="text.secondary">
                        {member.total_tickets} tickets
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {member.resolved_tickets} resolved
                      </Typography>
                      <SLAChip rate={member.sla_compliance_rate} />
                    </Stack>
                  </Box>
                ))}
              </Stack>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Recent tickets
              </Typography>
              {recentTickets.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No recent tickets.
                </Typography>
              ) : (
                <Box sx={{ overflowX: 'auto' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Redmine #</TableCell>
                        <TableCell>Subject</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Priority</TableCell>
                        <TableCell>Assignee</TableCell>
                        <TableCell>SLA</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Resolved</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {recentTickets.map((ticket) => (
                        <RecentTicketRow key={ticket.ticket_id} ticket={ticket} />
                      ))}
                    </TableBody>
                  </Table>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
