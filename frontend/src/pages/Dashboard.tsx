import { useNavigate } from 'react-router-dom';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  LinearProgress,
  Chip,
  IconButton,
  Paper,
  Stack,
  Divider,
  Tooltip,
  Zoom,
} from '@mui/material';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  People as PeopleIcon,
  Assignment as AssignmentIcon,
  Speed as SpeedIcon,
  Timer as TimerIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/services/api';
import type { WorkloadSummary, SLATracker, DashboardCardInsight, ActiveWorkSession } from '@/types';
import ActivityFeed from '@/components/ActivityFeed';
import InteractiveMetricCard from '@/components/InteractiveMetricCard';
import WorkSessionManager from '@/components/WorkSessionManager';
import { useDashboardMetrics } from '@/hooks/useDashboard';
import { queryKeys } from '@/lib/queryClient';

// Enhanced gradient colors for charts

interface SparklineStats {
  current: number;
  previous?: number;
  average: number;
  change?: number;
}

interface HoverOptions {
  unit?: string;
  precision?: number;
  averagePrecision?: number;
}

const calculateSparklineStats = (insight?: DashboardCardInsight): SparklineStats | null => {
  if (!insight?.sparkline?.length) return null;

  const values = insight.sparkline.map((point) => point.value);
  const current = values[values.length - 1];
  const previous = values.length > 1 ? values[values.length - 2] : undefined;
  const average = values.reduce((acc, value) => acc + value, 0) / values.length;

  let change: number | undefined;
  if (previous !== undefined) {
    if (previous === 0) {
      change = current === 0 ? 0 : 100;
    } else {
      change = ((current - previous) / previous) * 100;
    }
  }

  return {
    current,
    previous,
    average,
    change,
  };
};

const formatWithUnit = (value: number, decimals: number, unit?: string) => {
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  if (!unit) return formatted;
  if (unit === '%') return `${formatted}%`;
  return `${formatted} ${unit}`;
};

const buildHoverDetails = (
  insight?: DashboardCardInsight,
  stats?: SparklineStats | null,
  options: HoverOptions = {}
): string | undefined => {
  if (!insight || !stats) return undefined;

  const { unit, precision = 0, averagePrecision } = options;
  const avgPrecision = averagePrecision ?? Math.max(precision, 1);

  const latestLabel = insight.sparkline[insight.sparkline.length - 1]?.label;
  const previousLabel =
    insight.sparkline.length > 1 ? insight.sparkline[insight.sparkline.length - 2]?.label : undefined;

  const parts: string[] = [];
  const latestValue = formatWithUnit(stats.current, precision, unit);
  const averageValue = formatWithUnit(stats.average, avgPrecision, unit);

  parts.push(latestLabel ? `${latestLabel}: ${latestValue}` : `Latest: ${latestValue}`);
  parts.push(`7-day avg: ${averageValue}`);

  if (stats.change !== undefined) {
    const changeValue = Math.abs(stats.change).toFixed(1);
    const direction = stats.change >= 0 ? 'Up' : 'Down';
    const comparisonLabel = previousLabel ? previousLabel : 'prev day';
    parts.push(`${direction} ${changeValue}% vs ${comparisonLabel}`);
  }

  return parts.join(' | ');
};

const formatTrendLabel = (
  stats: SparklineStats | null,
  mode: 'count' | 'percent',
  fallback?: string,
  unitLabel?: string
): string | undefined => {
  if (!stats || stats.previous === undefined) return fallback;

  if (mode === 'percent') {
    const delta = stats.current - (stats.previous ?? 0);
    if (Math.abs(delta) < 0.05) {
      return fallback ?? 'No change vs prev day';
    }
    return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)} pts vs prev day`;
  }

  const deltaCount = stats.current - (stats.previous ?? 0);
  if (deltaCount === 0) {
    return fallback ?? 'No change vs prev day';
  }
  const unitText = unitLabel ? ` ${unitLabel}` : '';
  const formattedDelta = Math.abs(deltaCount).toLocaleString();
  return `${deltaCount >= 0 ? '+' : '-'}${formattedDelta}${unitText} vs prev day`;
};

export default function Dashboard() {
  const navigate = useNavigate();
  const {
    data: metrics,
    isLoading: metricsLoading,
    isFetching: metricsFetching,
    refetch: refetchMetrics,
    dataUpdatedAt: metricsUpdatedAt,
    error: metricsError,
  } = useDashboardMetrics();

  const {
    data: workload = [],
    isLoading: workloadLoading,
    isFetching: workloadFetching,
    refetch: refetchWorkload,
    error: workloadError,
  } = useQuery<WorkloadSummary[]>({
    queryKey: queryKeys.workload.current(),
    queryFn: async () => apiClient.getWorkload(),
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  });

  const {
    data: atRiskTickets = [],
    isLoading: atRiskLoading,
    isFetching: atRiskFetching,
    refetch: refetchAtRisk,
    error: atRiskError,
  } = useQuery<SLATracker[]>({
    queryKey: queryKeys.sla.atRisk(),
    queryFn: async () => apiClient.getAtRiskTickets(),
    refetchInterval: 1000 * 60,
  });

  const {
    data: activeWorkSessions = [],
    isLoading: activeSessionsLoading,
    isFetching: activeSessionsFetching,
    refetch: refetchActiveSessions,
    error: activeSessionsError,
  } = useQuery<ActiveWorkSession[]>({
    queryKey: queryKeys.workSessions.active(),
    queryFn: async () => {
      const response = await apiClient.getActiveWorkSessions();
      return response?.active_sessions ?? [];
    },
    refetchInterval: 1000 * 30,
  });

  const loading =
    metricsLoading || workloadLoading || atRiskLoading || activeSessionsLoading;
  const refreshing =
    metricsFetching || workloadFetching || atRiskFetching || activeSessionsFetching;
  const queryError =
    metricsError ?? workloadError ?? atRiskError ?? activeSessionsError;
  const lastRefreshLabel = metricsUpdatedAt
    ? format(new Date(metricsUpdatedAt), 'HH:mm:ss')
    : '--:--:--';

  const handleRefresh = async () => {
    await Promise.allSettled([
      refetchMetrics(),
      refetchWorkload(),
      refetchAtRisk(),
      refetchActiveSessions(),
    ]);
  };

  if (loading && !metrics) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (queryError) {
    console.error('Failed to load dashboard data:', queryError);
  }

  if (!metrics) {
    return (
      <Box p={3}>
        <Typography variant="h6" color="text.secondary">
          Dashboard data is unavailable right now.
        </Typography>
      </Box>
    );
  }

  if (loading || !metrics) {
    return (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress size={60} thickness={4} />
        <Typography variant="h6" color="text.secondary" sx={{ mt: 2 }}>
          Loading Dashboard...
        </Typography>
      </Box>
    );
  }

  // Prepare chart data
  const workloadChartData = workload
    .sort((a, b) => (b.capacity_percentage ?? 0) - (a.capacity_percentage ?? 0))
    .map((w) => ({
      name: w.member_name.split(' ')[0], // First name only for better display
      capacity: w.capacity_percentage ?? 0,
      tickets: w.current_tickets ?? 0,
      max: w.max_tickets ?? 0,
    }));

  const slaStatusData = [
    {
      name: 'Within SLA',
      value: Math.max(0, metrics.total_tickets_today - metrics.at_risk_tickets - metrics.critical_tickets),
      color: '#4caf50',
    },
    { name: 'At Risk', value: metrics.at_risk_tickets, color: '#ff9800' },
    { name: 'Critical', value: metrics.critical_tickets, color: '#f44336' },
  ];

  const cardInsights = metrics.card_insights;
  const totalTicketsInsight = cardInsights?.total_tickets;
  const slaInsight = cardInsights?.sla_compliance;
  const atRiskInsight = cardInsights?.at_risk;
  const capacityInsight = cardInsights?.team_capacity;

  const totalTicketsStats = calculateSparklineStats(totalTicketsInsight);
  const slaStats = calculateSparklineStats(slaInsight);
  const atRiskStats = calculateSparklineStats(atRiskInsight);
  const capacityStats = calculateSparklineStats(capacityInsight);

  const totalTicketsHover = buildHoverDetails(totalTicketsInsight, totalTicketsStats, {
    unit: 'tickets',
    precision: 0,
  });
  const slaHover = buildHoverDetails(slaInsight, slaStats, {
    unit: '%',
    precision: 1,
    averagePrecision: 1,
  });
  const atRiskHover = buildHoverDetails(atRiskInsight, atRiskStats, {
    unit: 'tickets',
    precision: 0,
  });
  const capacityHover = buildHoverDetails(capacityInsight, capacityStats, {
    unit: '%',
    precision: 1,
    averagePrecision: 1,
  });

  const totalTicketsTrendLabel = formatTrendLabel(totalTicketsStats, 'count', '+5 tickets vs prev day', 'tickets');
  const slaTrendLabel = formatTrendLabel(slaStats, 'percent', 'Excellent performance');
  const atRiskTrendLabel = formatTrendLabel(atRiskStats, 'count', '-2 tickets vs prev day', 'tickets');
  const capacityTrendLabel = formatTrendLabel(
    capacityStats,
    'percent',
    metrics.team_capacity_percentage > 80 ? 'High load' : 'Optimal'
  );

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real-time overview of your ticket management system
          </Typography>
        </Box>
        <Stack direction="row" spacing={2}>
          <Chip
            icon={<TimerIcon />}
            label={`Updated ${lastRefreshLabel}`}
            size="small"
            variant="outlined"
          />
          <Tooltip title="Refresh Dashboard">
            <IconButton
              onClick={handleRefresh}
              disabled={refreshing}
              sx={{
                bgcolor: 'primary.main',
                color: 'white',
                '&:hover': { bgcolor: 'primary.dark' },
              }}
            >
              {refreshing ? <CircularProgress size={24} color="inherit" /> : <RefreshIcon />}
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <InteractiveMetricCard
            title="Total Tickets Today"
            value={metrics.total_tickets_today.toLocaleString()}
            icon={<AssignmentIcon sx={{ fontSize: 32 }} />}
            gradient="linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
            subtitle={`${metrics.tickets_in_progress.toLocaleString()} in progress`}
            trendLabel={totalTicketsTrendLabel}
            hoverDetails={totalTicketsHover}
            insight={totalTicketsInsight}
            onDrillDown={() => navigate('/tickets?status=in_progress')}
            drillDownLabel="View in-progress tickets"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <InteractiveMetricCard
            title="SLA Compliance"
            value={`${metrics.sla_compliance_rate.toFixed(1)}%`}
            icon={<CheckCircleIcon sx={{ fontSize: 32 }} />}
            gradient="linear-gradient(135deg, #56ab2f 0%, #a8e063 100%)"
            subtitle={`Avg resolution ${metrics.avg_resolution_time_hours.toFixed(1)}h`}
            trendLabel={slaTrendLabel}
            hoverDetails={slaHover}
            insight={slaInsight}
            onDrillDown={() => navigate('/analytics?sla=overview')}
            drillDownLabel="Open SLA analytics"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <InteractiveMetricCard
            title="At Risk Tickets"
            value={(metrics.at_risk_tickets + metrics.critical_tickets).toLocaleString()}
            icon={<WarningIcon sx={{ fontSize: 32 }} />}
            gradient="linear-gradient(135deg, #f2994a 0%, #f2c94c 100%)"
            subtitle={`${metrics.critical_tickets.toLocaleString()} critical`}
            trendLabel={atRiskTrendLabel}
            hoverDetails={atRiskHover}
            insight={atRiskInsight}
            onDrillDown={() => navigate('/tickets?sla=at_risk')}
            drillDownLabel="View at-risk tickets"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <InteractiveMetricCard
            title="Team Capacity"
            value={`${metrics.team_capacity_percentage.toFixed(0)}%`}
            icon={<PeopleIcon sx={{ fontSize: 32 }} />}
            gradient={
              metrics.team_capacity_percentage > 80
                ? 'linear-gradient(135deg, #eb3349 0%, #f45c43 100%)'
                : 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
            }
            subtitle={`${metrics.active_collaborations.toLocaleString()} active collaborations`}
            trendLabel={capacityTrendLabel}
            hoverDetails={capacityHover}
            insight={capacityInsight}
            onDrillDown={() => navigate('/team')}
            drillDownLabel="Inspect team capacity"
          />
        </Grid>
      </Grid>

      {/* Active Work Sessions */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} lg={4}>
          <WorkSessionManager
            sessions={activeWorkSessions}
            maxSessions={2}
            loading={loading}
            onViewTicket={(ticketId) => navigate(`/tickets?id=${ticketId}`)}
          />
        </Grid>
        <Grid item xs={12} lg={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" fontWeight={600} gutterBottom>
                Work Efficiency Overview
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Real-time tracking of active work vs. waiting time across all tickets
              </Typography>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Active Sessions: {activeWorkSessions.length} / 2 per engineer
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={(activeWorkSessions.length / (workload.length * 2)) * 100}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
                <Stack direction="row" spacing={2} justifyContent="space-around">
                  <Box textAlign="center">
                    <Typography variant="h4" fontWeight={700} color="primary.main">
                      {activeWorkSessions.filter((s) => s.is_running).length}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Active Now
                    </Typography>
                  </Box>
                  <Divider orientation="vertical" flexItem />
                  <Box textAlign="center">
                    <Typography variant="h4" fontWeight={700} color="success.main">
                      {workload.filter((w) => (w.current_tickets ?? 0) > 0).length}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Engineers Working
                    </Typography>
                  </Box>
                  <Divider orientation="vertical" flexItem />
                  <Box textAlign="center">
                    <Typography variant="h4" fontWeight={700} color="warning.main">
                      {workload.filter((w) => (w.current_tickets ?? 0) === 0).length}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Available
                    </Typography>
                  </Box>
                </Stack>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts Row */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {/* Team Workload Chart */}
        <Grid item xs={12} lg={8}>
          <Card
            elevation={0}
            sx={{
              border: '1px solid',
              borderColor: 'grey.200',
              borderRadius: 2,
            }}
          >
              <CardContent sx={{ p: 3 }}>
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
                  <Box>
                    <Typography variant="h6" fontWeight={600}>
                      Team Workload Distribution
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Current tickets vs maximum capacity
                    </Typography>
                  </Box>
                  <SpeedIcon sx={{ fontSize: 32, color: 'primary.main' }} />
                </Box>
                <ResponsiveContainer width="100%" height={320}>
                  <BarChart data={workloadChartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                    <defs>
                      <linearGradient id="colorTickets" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#667eea" stopOpacity={0.9} />
                        <stop offset="95%" stopColor="#764ba2" stopOpacity={0.9} />
                      </linearGradient>
                      <linearGradient id="colorCapacity" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#e0e0e0" stopOpacity={0.8} />
                        <stop offset="95%" stopColor="#bdbdbd" stopOpacity={0.8} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="name"
                      angle={-45}
                      textAnchor="end"
                      height={80}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <RechartsTooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: 'none',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      }}
                    />
                    <Legend wrapperStyle={{ paddingTop: 10 }} />
                    <Bar dataKey="tickets" fill="url(#colorTickets)" name="Current Tickets" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="max" fill="url(#colorCapacity)" name="Max Capacity" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
        </Grid>

        {/* SLA Status Pie Chart */}
        <Grid item xs={12} lg={4}>
          <Card
            elevation={0}
            sx={{
              border: '1px solid',
              borderColor: 'grey.200',
              borderRadius: 2,
              height: '100%',
            }}
          >
              <CardContent sx={{ p: 3 }}>
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
                  <Box>
                    <Typography variant="h6" fontWeight={600}>
                      SLA Status
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Current distribution
                    </Typography>
                  </Box>
                  <TimerIcon sx={{ fontSize: 32, color: 'success.main' }} />
                </Box>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <defs>
                      {slaStatusData.map((entry, index) => (
                        <linearGradient key={index} id={`gradient-${index}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={entry.color} stopOpacity={0.9} />
                          <stop offset="95%" stopColor={entry.color} stopOpacity={0.7} />
                        </linearGradient>
                      ))}
                    </defs>
                    <Pie
                      data={slaStatusData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={90}
                      dataKey="value"
                    >
                      {slaStatusData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={`url(#gradient-${index})`} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      contentStyle={{
                        borderRadius: 8,
                        border: 'none',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
        </Grid>
      </Grid>

      {/* Bottom Row */}
      <Grid container spacing={3}>
        {/* At Risk Tickets */}
        <Grid item xs={12} lg={8}>
          <Card
            elevation={0}
              sx={{
                border: '1px solid',
                borderColor: 'grey.200',
                borderRadius: 2,
              }}
            >
              <CardContent sx={{ p: 3 }}>
                <Box display="flex" alignItems="center" gap={1.5} mb={3}>
                  <WarningIcon sx={{ fontSize: 28, color: 'warning.main' }} />
                  <Box>
                    <Typography variant="h6" fontWeight={600}>
                      At-Risk Tickets
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Tickets approaching SLA deadline
                    </Typography>
                  </Box>
                  <Chip
                    label={atRiskTickets.length}
                    size="small"
                    sx={{
                      ml: 'auto',
                      bgcolor: 'warning.light',
                      color: 'warning.dark',
                      fontWeight: 600,
                    }}
                  />
                </Box>

                {atRiskTickets.length === 0 ? (
                  <Paper
                    elevation={0}
                    sx={{
                      p: 4,
                      textAlign: 'center',
                      bgcolor: 'grey.50',
                      border: '2px dashed',
                      borderColor: 'grey.300',
                      borderRadius: 2,
                    }}
                  >
                    <CheckCircleIcon sx={{ fontSize: 48, color: 'success.main', mb: 1 }} />
                    <Typography variant="body1" color="text.secondary">
                      Great! No tickets at risk
                    </Typography>
                  </Paper>
                ) : (
                  <Stack spacing={2}>
                    {atRiskTickets.slice(0, 5).map((tracker, index) => (
                      <Zoom in key={tracker.id} timeout={300 + index * 100}>
                        <Paper
                          elevation={0}
                          sx={{
                            p: 2.5,
                            border: '1px solid',
                            borderColor: 'grey.200',
                            borderRadius: 2,
                            transition: 'all 0.3s ease',
                            '&:hover': {
                              borderColor: tracker.status === 'critical' ? 'error.main' : 'warning.main',
                              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                              transform: 'translateY(-2px)',
                            },
                          }}
                        >
                          <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1.5}>
                            <Box flex={1}>
                              <Typography variant="subtitle1" fontWeight={600}>
                                #{tracker.ticket?.redmine_ticket_id ?? '—'} - {tracker.ticket?.subject ?? 'Unknown'}
                              </Typography>
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                {tracker.ticket?.priority ?? 'Unknown'} | {tracker.ticket?.assigned_to?.name || 'Unassigned'}
                              </Typography>
                            </Box>
                            <Chip
                              label={(tracker.status ?? 'unknown').replace('_', ' ').toUpperCase()}
                              size="small"
                              sx={{
                                bgcolor: tracker.status === 'critical' ? 'error.light' : 'warning.light',
                                color: tracker.status === 'critical' ? 'error.dark' : 'warning.dark',
                                fontWeight: 600,
                              }}
                            />
                          </Box>

                          <Box>
                            <Box display="flex" justifyContent="space-between" mb={0.5}>
                              <Typography variant="caption" color="text.secondary">
                                Time Remaining: {tracker.time_remaining_minutes ?? 'N/A'} minutes
                              </Typography>
                              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                {(tracker.completion_percentage ?? 0).toFixed(0)}% elapsed
                              </Typography>
                            </Box>
                            <LinearProgress
                              variant="determinate"
                              value={tracker.completion_percentage ?? 0}
                              sx={{
                                height: 8,
                                borderRadius: 4,
                                bgcolor: 'grey.200',
                                '& .MuiLinearProgress-bar': {
                                  bgcolor: (tracker.completion_percentage ?? 0) >= 90 ? 'error.main' : 'warning.main',
                                  borderRadius: 4,
                                },
                              }}
                            />
                          </Box>
                        </Paper>
                      </Zoom>
                    ))}
                  </Stack>
                )}
              </CardContent>
            </Card>
        </Grid>

        {/* Real-time Activity Feed */}
        <Grid item xs={12} lg={4}>
          <ActivityFeed limit={15} hours={24} autoRefresh={true} refreshInterval={30000} />
        </Grid>
      </Grid>
    </Box>
  );
}
