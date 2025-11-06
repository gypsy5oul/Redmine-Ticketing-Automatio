import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Stack,
  Button,
  Tooltip as MuiTooltip,
  Snackbar,
  Alert,
} from '@mui/material'
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { format, subDays } from 'date-fns'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import ScienceIcon from '@mui/icons-material/Science'
import WorkIcon from '@mui/icons-material/Work'
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty'
import PersonOffIcon from '@mui/icons-material/PersonOff'
import apiClient from '@/services/api'
import type {
  TicketVolumeData,
  TeamPerformanceData,
  MLTrainingResult,
  MLModelsStatusResponse,
  Ticket,
} from '@/types'
import WorkEfficiencyChart from '@/components/WorkEfficiencyChart'

export default function Analytics() {
  const [loading, setLoading] = useState(true)
  const [forecastData, setForecastData] = useState<TicketVolumeData[]>([])
  const [teamPerformance, setTeamPerformance] = useState<TeamPerformanceData[]>([])
  const [workSessionTickets, setWorkSessionTickets] = useState<Ticket[]>([])
  const [dateRange, setDateRange] = useState(7)
  const [training, setTraining] = useState(false)
  const [trainingResult, setTrainingResult] = useState<MLTrainingResult | null>(null)
  const [trainingError, setTrainingError] = useState<string | null>(null)
  const [modelsStatus, setModelsStatus] = useState<MLModelsStatusResponse | null>(null)
  const [statusLoading, setStatusLoading] = useState(false)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' | 'warning' })

  const fetchAnalyticsData = useCallback(async () => {
    try {
      setLoading(true)
      const endDate = new Date()
      const startDate = subDays(endDate, dateRange)

      const [forecastResult, performanceResult, ticketsResult] = await Promise.all([
        apiClient.getTicketVolumeForecast(dateRange),
        apiClient.getTeamPerformance(
          format(startDate, 'yyyy-MM-dd'),
          format(endDate, 'yyyy-MM-dd')
        ),
        apiClient.getTickets({}).catch(() => ({ tickets: [] as Ticket[] })),
      ])

      const combinedForecast = [...forecastResult].sort(
        (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime(),
      )

      setForecastData(combinedForecast)
      setTeamPerformance(performanceResult)
      setWorkSessionTickets(Array.isArray(ticketsResult) ? ticketsResult : (ticketsResult.tickets || []))
    } catch (error) {
      console.error('Failed to fetch analytics data:', error)
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  const fetchMLStatus = useCallback(async () => {
    try {
      setStatusLoading(true)
      const status = await apiClient.getMLModelsStatus()
      setModelsStatus(status)
    } catch (error) {
      console.error('Failed to fetch ML model status:', error)
    } finally {
      setStatusLoading(false)
    }
  }, [])

  const handleTrainModels = useCallback(async () => {
    try {
      setTraining(true)
      setTrainingError(null)
      const result = await apiClient.trainMLModels()
      setTrainingResult(result)

      if (result.success) {
        setSnackbar({ open: true, message: 'ML models retrained successfully', severity: 'success' })
        await fetchMLStatus()
        await fetchAnalyticsData()
      } else {
        const errorMessage = result.error || 'ML training failed'
        setTrainingError(errorMessage)
        setSnackbar({ open: true, message: errorMessage, severity: 'error' })
      }
    } catch (error: any) {
      console.error('Failed to trigger ML training:', error)

      // Handle specific error messages from API
      const errorDetail = error.response?.data?.detail
      let userMessage = 'Failed to trigger ML training'

      const currentCount = error.response?.data?.current_count

      if (errorDetail) {
        if (errorDetail.includes('at least') || errorDetail.includes('Need at least')) {
          const countText = typeof currentCount === 'number' ? `${currentCount}` : '0'
          userMessage = `Cannot train yet: ${errorDetail}. Currently have ${countText} tickets.`
        } else {
          userMessage = errorDetail
        }
      }

      setTrainingError(userMessage)
      setSnackbar({
        open: true,
        message: userMessage,
        severity: errorDetail?.includes('at least') ? 'warning' : 'error'
      })
    } finally {
      setTraining(false)
    }
  }, [fetchMLStatus, fetchAnalyticsData])

  const handleSnackbarClose = useCallback(() => {
    setSnackbar((prev) => ({ ...prev, open: false }))
  }, [])

  useEffect(() => {
    fetchAnalyticsData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateRange])

  useEffect(() => {
    fetchMLStatus()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const lastModelUpdated = useMemo(() => {
    if (!modelsStatus) return null
    return Object.values(modelsStatus.models).reduce<Date | null>((latest, model) => {
      if (!model.exists || !model.last_modified) return latest
      const current = new Date(model.last_modified)
      return !latest || current > latest ? current : latest
    }, null)
  }, [modelsStatus])

  const missingModels = useMemo(
    () =>
      modelsStatus
        ? Object.entries(modelsStatus.models)
            .filter(([, status]) => !status.exists)
            .map(([name]) => name)
        : [],
    [modelsStatus]
  )

  const modelsReady = modelsStatus?.all_present ?? false

  const modelStatusChipLabel = statusLoading
    ? 'Checking models...'
    : modelsStatus
    ? modelsReady
      ? `Models ready${lastModelUpdated ? ` · ${format(lastModelUpdated, 'MMM d HH:mm')}` : ''}`
      : 'Model artifacts missing'
    : 'Model status unavailable'

  const modelStatusChipColor: 'default' | 'success' | 'warning' = statusLoading
    ? 'default'
    : modelsStatus
    ? modelsReady
      ? 'success'
      : 'warning'
    : 'default'

  const sanitizeNumber = useCallback((value: number | null | undefined) => {
    return typeof value === 'number' && Number.isFinite(value) ? value : 0
  }, [])

  // Separate historical and forecast data - with defensive checks
  const historicalData = useMemo(() => {
    return Array.isArray(forecastData) ? forecastData.filter((d) => d && !d.predicted) : []
  }, [forecastData])

  const forecastOnlyData = useMemo(() => {
    return Array.isArray(forecastData) ? forecastData.filter((d) => d && d.predicted) : []
  }, [forecastData])

  // Calculate trends - with defensive checks
  const totalTicketsLast7Days = useMemo(() => {
    return historicalData.reduce((sum, d) => sum + (d?.count || 0), 0)
  }, [historicalData])

  const avgTicketsPerDay = useMemo(() => {
    return historicalData.length > 0 ? totalTicketsLast7Days / historicalData.length : 0
  }, [historicalData.length, totalTicketsLast7Days])

  const forecastedTotal = useMemo(() => {
    return forecastOnlyData.reduce((sum, d) => sum + (d?.count || 0), 0)
  }, [forecastOnlyData])

  const trendPercentage = useMemo(() => {
    return totalTicketsLast7Days > 0
      ? ((forecastedTotal - totalTicketsLast7Days) / totalTicketsLast7Days) * 100
      : 0
  }, [totalTicketsLast7Days, forecastedTotal]
  )

  // Prepare resolution time trend data
  const resolutionTrend = useMemo(() => {
    const performance = Array.isArray(teamPerformance) ? teamPerformance : []
    return performance.map((member) => ({
      name: member.member_name || 'Unknown',
      hours: sanitizeNumber(member.avg_resolution_time),
    }))
  }, [teamPerformance, sanitizeNumber])

  // Prepare SLA compliance data
  const slaComplianceData = useMemo(() => {
    const performance = Array.isArray(teamPerformance) ? teamPerformance : []
    return performance.map((member) => ({
      name: member.member_name || 'Unknown',
      compliance: sanitizeNumber(member.sla_compliance_rate),
      tickets: member.tickets_resolved ?? 0,
    }))
  }, [teamPerformance, sanitizeNumber])

  const averageSlaCompliance = useMemo(() => {
    const performance = Array.isArray(teamPerformance) ? teamPerformance : []
    if (!performance.length) {
      return 0
    }
    const total = performance.reduce(
      (sum, member) => sum + sanitizeNumber(member.sla_compliance_rate),
      0
    )
    return total / performance.length
  }, [teamPerformance, sanitizeNumber])

  // Calculate work session analytics
  const workSessionAnalytics = useMemo(() => {
    // Defensive check - ensure workSessionTickets is an array
    const tickets = Array.isArray(workSessionTickets) ? workSessionTickets : []

    const totalWork = tickets.reduce((sum, t) => sum + (t.total_work_minutes || 0), 0)
    const totalWaiting = tickets.reduce((sum, t) => sum + (t.total_waiting_minutes || 0), 0)
    const totalIdle = tickets.reduce((sum, t) => sum + (t.total_idle_minutes || 0), 0)

    const ticketsWithWork = tickets.filter((t) => (t.total_work_minutes || 0) > 0)
    const avgEfficiency = ticketsWithWork.length > 0
      ? ticketsWithWork.reduce((sum, t) => sum + (t.work_efficiency_percent || 0), 0) / ticketsWithWork.length
      : 0

    // Bottleneck analysis - what causes most waiting
    const waitingReasons: Record<string, number> = {}
    tickets.forEach((ticket) => {
      // Defensive check - ensure work_summary and work_sessions exist
      if (ticket.work_summary?.work_sessions && Array.isArray(ticket.work_summary.work_sessions)) {
        ticket.work_summary.work_sessions.forEach((session) => {
          if (session.type && session.type.startsWith('waiting_') && session.duration_minutes) {
            const reason = session.type.replace('waiting_', '')
            waitingReasons[reason] = (waitingReasons[reason] || 0) + session.duration_minutes
          }
        })
      }
    })

    // Convert to array and sort - ensure stable output even when empty
    const bottleneckData = Object.entries(waitingReasons).length > 0
      ? Object.entries(waitingReasons)
          .map(([reason, minutes]) => ({
            name: reason.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
            minutes,
            hours: Math.round((minutes / 60) * 10) / 10,
          }))
          .sort((a, b) => b.minutes - a.minutes)
      : [] // Return empty array if no data

    return {
      totalWork,
      totalWaiting,
      totalIdle,
      avgEfficiency,
      bottleneckData,
      ticketsWithWork: ticketsWithWork.length,
    }
  }, [workSessionTickets])

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Stack
        direction={{ xs: 'column', md: 'row' }}
        spacing={2}
        justifyContent="space-between"
        alignItems={{ xs: 'flex-start', md: 'center' }}
        mb={3}
      >
        <Typography variant="h4">Analytics & Forecasting</Typography>
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1.5}
          alignItems={{ xs: 'flex-start', md: 'center' }}
        >
          <FormControl sx={{ minWidth: 200 }}>
            <InputLabel>Date Range</InputLabel>
            <Select
              value={dateRange}
              label="Date Range"
              onChange={(e) => setDateRange(e.target.value as number)}
            >
              <MenuItem value={7}>Last 7 Days</MenuItem>
              <MenuItem value={14}>Last 14 Days</MenuItem>
              <MenuItem value={30}>Last 30 Days</MenuItem>
              <MenuItem value={90}>Last 90 Days</MenuItem>
            </Select>
          </FormControl>
          <MuiTooltip title={modelStatusChipLabel} placement="bottom">
            <Chip label={modelStatusChipLabel} color={modelStatusChipColor} variant="outlined" />
          </MuiTooltip>
          <MuiTooltip title="Train machine learning models with the latest resolved tickets" placement="bottom">
            <span>
              <Button
                variant="contained"
                color="secondary"
                startIcon={
                  training ? <CircularProgress size={18} color="inherit" /> : <ScienceIcon />
                }
                onClick={handleTrainModels}
                disabled={training}
              >
                {training ? 'Training...' : 'Train ML Models'}
              </Button>
            </span>
          </MuiTooltip>
        </Stack>
      </Stack>

      {trainingError && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {trainingError}
        </Alert>
      )}

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom variant="body2">
                Avg Tickets/Day
              </Typography>
              <Typography variant="h4" component="div" sx={{ fontWeight: 'bold' }}>
                {avgTicketsPerDay.toFixed(1)}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Last {historicalData.length} days
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom variant="body2">
                Forecasted (7d)
              </Typography>
              <Typography variant="h4" component="div" sx={{ fontWeight: 'bold' }}>
                {forecastedTotal}
              </Typography>
              <Box display="flex" alignItems="center" mt={1}>
                {trendPercentage > 0 ? (
                  <>
                    <TrendingUpIcon color="error" fontSize="small" />
                    <Typography variant="caption" color="error">
                      +{trendPercentage.toFixed(1)}% vs last week
                    </Typography>
                  </>
                ) : (
                  <>
                    <TrendingDownIcon color="success" fontSize="small" />
                    <Typography variant="caption" color="success">
                      {trendPercentage.toFixed(1)}% vs last week
                    </Typography>
                  </>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom variant="body2">
                Team Performance
              </Typography>
              <Typography variant="h4" component="div" sx={{ fontWeight: 'bold' }}>
                {teamPerformance.length}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Active team members
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography color="textSecondary" gutterBottom variant="body2">
                Avg SLA Compliance
              </Typography>
              <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                {averageSlaCompliance.toFixed(1)}
                %
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Across all teams
              </Typography>
            </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={6} lg={4}>
        <Card>
          <CardContent>
            <Typography color="textSecondary" gutterBottom variant="body2">
              ML Models Overview
            </Typography>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {statusLoading
                ? 'Validating model artifacts...'
                : modelsReady
                ? 'All model artifacts are present'
                : 'Some model artifacts are missing'}
            </Typography>
            {statusLoading ? (
              <Box display="flex" alignItems="center" gap={1}>
                <CircularProgress size={18} />
                <Typography variant="body2">Checking model directory…</Typography>
              </Box>
            ) : (
              <Stack spacing={1} maxHeight={180} sx={{ overflowY: 'auto', pr: 1 }}>
                {Object.entries(modelsStatus?.models ?? {}).map(([name, status]) => (
                  <Stack key={name} direction="row" spacing={1} alignItems="center">
                    <Chip
                      label={status.exists ? 'Ready' : 'Missing'}
                      size="small"
                      color={status.exists ? 'success' : 'warning'}
                    />
                    <Typography variant="body2" sx={{ flexGrow: 1 }}>
                      {name.replace('.joblib', '')}
                    </Typography>
                    {status.exists && status.last_modified && (
                      <MuiTooltip title={format(new Date(status.last_modified), 'yyyy-MM-dd HH:mm:ss')}>
                        <Typography variant="caption" color="text.secondary">
                          {format(new Date(status.last_modified), 'MMM d HH:mm')}
                        </Typography>
                      </MuiTooltip>
                    )}
                  </Stack>
                ))}
                {modelsStatus && Object.keys(modelsStatus.models).length === 0 && (
                  <Typography variant="body2" color="text.secondary">
                    No model artifacts detected in {modelsStatus.models_path}
                  </Typography>
                )}
                {missingModels.length > 0 && (
                  <Alert severity="warning" variant="outlined" sx={{ mt: 1 }}>
                    Missing files: {missingModels.join(', ')}
                  </Alert>
                )}
                {modelsReady && lastModelUpdated && (
                  <Alert severity="success" variant="outlined" sx={{ mt: 1 }}>
                    Last trained {format(lastModelUpdated, 'MMM d, yyyy HH:mm')}
                  </Alert>
                )}
                {trainingResult?.success && trainingResult.trained_at && (
                  <Typography variant="caption" color="text.secondary">
                    Models retrained on {format(new Date(trainingResult.trained_at), 'MMM d, yyyy HH:mm')}
                  </Typography>
                )}
              </Stack>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>

      {/* Ticket Volume Forecast */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">Ticket Volume Forecast (7 Days)</Typography>
                <Box display="flex" gap={1}>
                  <Chip label="Historical" size="small" sx={{ bgcolor: '#1976d2', color: 'white' }} />
                  <Chip label="Predicted" size="small" sx={{ bgcolor: '#ff9800', color: 'white' }} />
                </Box>
              </Box>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart data={forecastData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => format(new Date(value), 'MM/dd')}
                  />
                  <YAxis />
                  <RechartsTooltip
                    labelFormatter={(value) => format(new Date(value), 'MMM dd, yyyy')}
                    formatter={(value: number, name: string) => [
                      value,
                      name === 'count' ? 'Tickets' : name,
                    ]}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#1976d2"
                    fill="#1976d2"
                    fillOpacity={0.6}
                    name="Ticket Count"
                  />
                </AreaChart>
              </ResponsiveContainer>
              <Typography variant="caption" color="textSecondary" sx={{ mt: 2, display: 'block' }}>
                * Prediction based on ML model trained on historical ticket patterns
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Team Performance Charts */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Average Resolution Time by Team Member
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={resolutionTrend}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                  <YAxis label={{ value: 'Hours', angle: -90, position: 'insideLeft' }} />
                  <RechartsTooltip />
                  <Bar dataKey="hours" fill="#1976d2" name="Avg Resolution Time (hrs)" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                SLA Compliance Rate by Team Member
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={slaComplianceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                  <YAxis
                    domain={[0, 100]}
                    label={{ value: 'Compliance %', angle: -90, position: 'insideLeft' }}
                  />
                  <RechartsTooltip />
                  <Bar dataKey="compliance" fill="#4caf50" name="SLA Compliance %" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Work Session Analytics */}
      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h5" fontWeight={600} gutterBottom>
                Work Efficiency Analytics
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Analysis of active work time vs. waiting time across all tickets
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Summary Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                <WorkIcon color="primary" />
                <Typography variant="body2" color="text.secondary">
                  Total Active Work
                </Typography>
              </Stack>
              <Typography variant="h4" fontWeight={700} color="primary.main">
                {Math.round(workSessionAnalytics.totalWork / 60)}h
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {workSessionAnalytics.totalWork} minutes across {workSessionAnalytics.ticketsWithWork} tickets
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                <HourglassEmptyIcon color="warning" />
                <Typography variant="body2" color="text.secondary">
                  Total Waiting Time
                </Typography>
              </Stack>
              <Typography variant="h4" fontWeight={700} color="warning.main">
                {Math.round(workSessionAnalytics.totalWaiting / 60)}h
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {workSessionAnalytics.totalWaiting} minutes waiting for external factors
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                <PersonOffIcon />
                <Typography variant="body2" color="text.secondary">
                  Idle Time
                </Typography>
              </Stack>
              <Typography variant="h4" fontWeight={700}>
                {Math.round(workSessionAnalytics.totalIdle / 60)}h
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {workSessionAnalytics.totalIdle} minutes assigned but not started
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                <TrendingUpIcon color="success" />
                <Typography variant="body2" color="text.secondary">
                  Avg Efficiency
                </Typography>
              </Stack>
              <Typography variant="h4" fontWeight={700} color="success.main">
                {workSessionAnalytics.avgEfficiency.toFixed(1)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Work time / (Work + Waiting) across tickets
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Bottleneck Analysis Chart */}
        {workSessionAnalytics.bottleneckData.length > 0 && (
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Bottleneck Analysis - What Causes Waiting
                </Typography>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={workSessionAnalytics.bottleneckData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" label={{ value: 'Hours', position: 'bottom' }} />
                    <YAxis dataKey="name" type="category" width={150} />
                    <RechartsTooltip
                      formatter={(value: number) => [`${value} hours`, 'Time Spent']}
                    />
                    <Bar dataKey="hours" fill="#ff9800" name="Waiting Time (hours)" />
                  </BarChart>
                </ResponsiveContainer>
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                  Identifies primary reasons for work delays across all tickets
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Work Efficiency Distribution */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Overall Time Distribution
              </Typography>
              <WorkEfficiencyChart
                totalWorkMinutes={workSessionAnalytics.totalWork}
                totalWaitingMinutes={workSessionAnalytics.totalWaiting}
                totalIdleMinutes={workSessionAnalytics.totalIdle}
                workEfficiencyPercent={workSessionAnalytics.avgEfficiency}
                variant="full"
                showLegend={true}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Team Performance Table */}
      <Grid container spacing={3} sx={{ mt: 1 }}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Detailed Team Performance
              </Typography>
              <Box sx={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                      <th style={{ textAlign: 'left', padding: '12px' }}>Team Member</th>
                      <th style={{ textAlign: 'left', padding: '12px' }}>Level</th>
                      <th style={{ textAlign: 'center', padding: '12px' }}>Tickets Resolved</th>
                      <th style={{ textAlign: 'center', padding: '12px' }}>Avg Resolution Time</th>
                      <th style={{ textAlign: 'center', padding: '12px' }}>SLA Compliance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamPerformance.map((member) => {
                      const avgResolution = sanitizeNumber(member.avg_resolution_time)
                      const slaRate = sanitizeNumber(member.sla_compliance_rate)
                      const slaColor =
                        slaRate >= 90
                          ? 'success.main'
                          : slaRate >= 70
                          ? 'warning.main'
                          : 'error.main'

                      return (
                        <tr
                          key={member.member_id}
                          style={{ borderBottom: '1px solid #e0e0e0' }}
                        >
                          <td style={{ padding: '12px' }}>
                            <Typography variant="body2">{member.member_name}</Typography>
                          </td>
                          <td style={{ padding: '12px' }}>
                            <Chip
                              label={member.team_level}
                              size="small"
                              color={
                                member.team_level === 'L1'
                                  ? 'success'
                                  : member.team_level === 'L2'
                                  ? 'primary'
                                  : 'secondary'
                              }
                            />
                          </td>
                          <td style={{ textAlign: 'center', padding: '12px' }}>
                            <Typography variant="body2">{member.tickets_resolved}</Typography>
                          </td>
                          <td style={{ textAlign: 'center', padding: '12px' }}>
                            <Typography variant="body2">
                              {avgResolution.toFixed(1)} hrs
                            </Typography>
                          </td>
                          <td style={{ textAlign: 'center', padding: '12px' }}>
                            <Typography variant="body2" color={slaColor}>
                              {slaRate.toFixed(1)}%
                            </Typography>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}
