import { Box, Typography, Stack, Paper, LinearProgress, Tooltip, Chip } from '@mui/material';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip as RechartsTooltip } from 'recharts';
import WorkIcon from '@mui/icons-material/Work';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';

interface WorkEfficiencyChartProps {
  totalWorkMinutes: number;
  totalWaitingMinutes: number;
  totalIdleMinutes: number;
  workEfficiencyPercent?: number | null;
  variant?: 'full' | 'compact' | 'minimal';
  showLegend?: boolean;
}

const formatDuration = (minutes: number): string => {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (remainingMinutes === 0) return `${hours}h`;
  return `${hours}h ${remainingMinutes}m`;
};

const getEfficiencyColor = (percent: number): string => {
  if (percent >= 70) return '#4caf50'; // Green
  if (percent >= 50) return '#ff9800'; // Orange
  return '#f44336'; // Red
};

const getEfficiencyLabel = (percent: number): string => {
  if (percent >= 70) return 'Excellent';
  if (percent >= 50) return 'Good';
  if (percent >= 30) return 'Fair';
  return 'Needs Improvement';
};

export default function WorkEfficiencyChart({
  totalWorkMinutes,
  totalWaitingMinutes,
  totalIdleMinutes,
  workEfficiencyPercent,
  variant = 'full',
  showLegend = true,
}: WorkEfficiencyChartProps) {
  const totalMinutes = totalWorkMinutes + totalWaitingMinutes + totalIdleMinutes;

  // Calculate percentages
  const workPercent = totalMinutes > 0 ? (totalWorkMinutes / totalMinutes) * 100 : 0;
  const waitPercent = totalMinutes > 0 ? (totalWaitingMinutes / totalMinutes) * 100 : 0;
  const idlePercent = totalMinutes > 0 ? (totalIdleMinutes / totalMinutes) * 100 : 0;

  // Use provided efficiency or calculate it
  const efficiency = workEfficiencyPercent ?? (totalWorkMinutes + totalWaitingMinutes > 0
    ? (totalWorkMinutes / (totalWorkMinutes + totalWaitingMinutes)) * 100
    : 0);

  const chartData = [
    { name: 'Active Work', value: totalWorkMinutes, color: '#4caf50' },
    { name: 'Waiting', value: totalWaitingMinutes, color: '#ff9800' },
    { name: 'Idle', value: totalIdleMinutes, color: '#9e9e9e' },
  ].filter((item) => item.value > 0);

  // Minimal variant - just the efficiency percentage
  if (variant === 'minimal') {
    return (
      <Chip
        icon={<TrendingUpIcon />}
        label={`${efficiency.toFixed(0)}% efficient`}
        color={efficiency >= 70 ? 'success' : efficiency >= 50 ? 'warning' : 'error'}
        size="small"
      />
    );
  }

  // Compact variant - efficiency bar and basic stats
  if (variant === 'compact') {
    return (
      <Stack spacing={1}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="body2" fontWeight={600}>
            Work Efficiency
          </Typography>
          <Typography variant="body2" fontWeight={700} color={getEfficiencyColor(efficiency)}>
            {efficiency.toFixed(1)}%
          </Typography>
        </Stack>
        <LinearProgress
          variant="determinate"
          value={efficiency}
          sx={{
            height: 8,
            borderRadius: 1,
            bgcolor: 'grey.200',
            '& .MuiLinearProgress-bar': {
              bgcolor: getEfficiencyColor(efficiency),
            },
          }}
        />
        <Stack direction="row" spacing={1} justifyContent="space-between">
          <Tooltip title="Active work time">
            <Chip
              icon={<WorkIcon />}
              label={formatDuration(totalWorkMinutes)}
              size="small"
              variant="outlined"
              sx={{ borderColor: '#4caf50', color: '#4caf50' }}
            />
          </Tooltip>
          <Tooltip title="Waiting time">
            <Chip
              icon={<HourglassEmptyIcon />}
              label={formatDuration(totalWaitingMinutes)}
              size="small"
              variant="outlined"
              sx={{ borderColor: '#ff9800', color: '#ff9800' }}
            />
          </Tooltip>
          {totalIdleMinutes > 0 && (
            <Tooltip title="Idle time">
              <Chip
                icon={<PersonOffIcon />}
                label={formatDuration(totalIdleMinutes)}
                size="small"
                variant="outlined"
                sx={{ borderColor: '#9e9e9e', color: '#9e9e9e' }}
              />
            </Tooltip>
          )}
        </Stack>
      </Stack>
    );
  }

  // Full variant - complete visualization
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2}>
        {/* Header */}
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="h6" fontWeight={600}>
            Work Efficiency Analysis
          </Typography>
          <Chip
            label={getEfficiencyLabel(efficiency)}
            color={efficiency >= 70 ? 'success' : efficiency >= 50 ? 'warning' : 'error'}
            size="small"
          />
        </Stack>

        {/* Efficiency Score */}
        <Box>
          <Stack direction="row" alignItems="baseline" spacing={1} mb={1}>
            <Typography variant="h3" fontWeight={700} color={getEfficiencyColor(efficiency)}>
              {efficiency.toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              efficiency
            </Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            Based on active work time vs. total engaged time (work + waiting)
          </Typography>
        </Box>

        {/* Pie Chart */}
        {chartData.length > 0 && (
          <Box sx={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip
                  formatter={(value: number) => formatDuration(value)}
                  contentStyle={{
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    border: '1px solid #ccc',
                    borderRadius: 4,
                  }}
                />
                {showLegend && <Legend />}
              </PieChart>
            </ResponsiveContainer>
          </Box>
        )}

        {/* Time Breakdown */}
        <Stack spacing={1}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              <Box sx={{ width: 12, height: 12, borderRadius: 1, bgcolor: '#4caf50' }} />
              <Typography variant="body2">Active Work</Typography>
            </Stack>
            <Stack direction="row" alignItems="baseline" spacing={0.5}>
              <Typography variant="body2" fontWeight={600}>
                {formatDuration(totalWorkMinutes)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({workPercent.toFixed(0)}%)
              </Typography>
            </Stack>
          </Stack>

          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              <Box sx={{ width: 12, height: 12, borderRadius: 1, bgcolor: '#ff9800' }} />
              <Typography variant="body2">Waiting Time</Typography>
            </Stack>
            <Stack direction="row" alignItems="baseline" spacing={0.5}>
              <Typography variant="body2" fontWeight={600}>
                {formatDuration(totalWaitingMinutes)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({waitPercent.toFixed(0)}%)
              </Typography>
            </Stack>
          </Stack>

          {totalIdleMinutes > 0 && (
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Stack direction="row" alignItems="center" spacing={1}>
                <Box sx={{ width: 12, height: 12, borderRadius: 1, bgcolor: '#9e9e9e' }} />
                <Typography variant="body2">Idle Time</Typography>
              </Stack>
              <Stack direction="row" alignItems="baseline" spacing={0.5}>
                <Typography variant="body2" fontWeight={600}>
                  {formatDuration(totalIdleMinutes)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ({idlePercent.toFixed(0)}%)
                </Typography>
              </Stack>
            </Stack>
          )}

          <Stack direction="row" alignItems="center" justifyContent="space-between" pt={1} borderTop={1} borderColor="divider">
            <Typography variant="body2" fontWeight={600}>
              Total Time
            </Typography>
            <Typography variant="body2" fontWeight={600}>
              {formatDuration(totalMinutes)}
            </Typography>
          </Stack>
        </Stack>
      </Stack>
    </Paper>
  );
}
