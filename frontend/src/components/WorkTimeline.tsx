import { Box, Typography, Stack, Chip, Paper, Divider } from '@mui/material';
import { format, parseISO } from 'date-fns';
import WorkIcon from '@mui/icons-material/Work';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PauseCircleIcon from '@mui/icons-material/PauseCircle';
import PersonOffIcon from '@mui/icons-material/PersonOff';
import type { WorkSession, WorkSessionType } from '@/types';

interface WorkTimelineProps {
  sessions: WorkSession[];
  showNotes?: boolean;
  compact?: boolean;
}

const SESSION_CONFIG: Record<
  WorkSessionType,
  { label: string; color: string; icon: JSX.Element }
> = {
  active_work: {
    label: 'Active Work',
    color: '#4caf50',
    icon: <WorkIcon fontSize="small" />,
  },
  waiting_customer: {
    label: 'Waiting for Customer',
    color: '#ff9800',
    icon: <HourglassEmptyIcon fontSize="small" />,
  },
  waiting_approval: {
    label: 'Waiting for Approval',
    color: '#ff9800',
    icon: <PauseCircleIcon fontSize="small" />,
  },
  waiting_deployment: {
    label: 'Waiting for Deployment',
    color: '#ff9800',
    icon: <HourglassEmptyIcon fontSize="small" />,
  },
  waiting_external: {
    label: 'Waiting on External Team',
    color: '#ff9800',
    icon: <HourglassEmptyIcon fontSize="small" />,
  },
  idle: {
    label: 'Idle (Not Started)',
    color: '#9e9e9e',
    icon: <PersonOffIcon fontSize="small" />,
  },
};

const formatDuration = (minutes: number): string => {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (remainingMinutes === 0) return `${hours}h`;
  return `${hours}h ${remainingMinutes}m`;
};

const formatDateTime = (dateString: string | null): string => {
  if (!dateString) return 'N/A';
  try {
    return format(parseISO(dateString), 'MMM dd, yyyy • HH:mm');
  } catch {
    return 'Invalid Date';
  }
};

const formatTime = (dateString: string | null): string => {
  if (!dateString) return 'N/A';
  try {
    return format(parseISO(dateString), 'HH:mm');
  } catch {
    return 'Invalid';
  }
};

export default function WorkTimeline({ sessions, showNotes = false, compact = false }: WorkTimelineProps) {
  if (sessions.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No work sessions recorded yet.
        </Typography>
      </Paper>
    );
  }

  // Sort sessions by start time (most recent first)
  const sortedSessions = [...sessions].sort((a, b) => {
    const timeA = a.started_at ? new Date(a.started_at).getTime() : 0;
    const timeB = b.started_at ? new Date(b.started_at).getTime() : 0;
    return timeB - timeA;
  });

  if (compact) {
    return (
      <Stack spacing={1}>
        {sortedSessions.map((session) => {
          const config = SESSION_CONFIG[session.type as WorkSessionType] || SESSION_CONFIG.active_work;
          return (
            <Stack key={session.id} direction="row" spacing={1} alignItems="center">
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  bgcolor: config.color,
                  flexShrink: 0,
                }}
              />
              <Typography variant="caption" color="text.secondary" sx={{ minWidth: 80 }}>
                {formatTime(session.started_at)}
              </Typography>
              <Chip label={config.label} size="small" sx={{ bgcolor: config.color + '20' }} />
              <Typography variant="caption" fontWeight={600}>
                {formatDuration(session.duration_minutes)}
              </Typography>
            </Stack>
          );
        })}
      </Stack>
    );
  }

  return (
    <Box sx={{ position: 'relative' }}>
      {/* Timeline Line */}
      <Box
        sx={{
          position: 'absolute',
          left: 20,
          top: 0,
          bottom: 0,
          width: 2,
          bgcolor: 'divider',
        }}
      />

      {/* Timeline Items */}
      <Stack spacing={3}>
        {sortedSessions.map((session) => {
          const config = SESSION_CONFIG[session.type as WorkSessionType] || SESSION_CONFIG.active_work;
          const isActive = session.is_active;

          return (
            <Box key={session.id} sx={{ position: 'relative', pl: 6 }}>
              {/* Timeline Dot */}
              <Box
                sx={{
                  position: 'absolute',
                  left: 12,
                  top: 4,
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  bgcolor: config.color,
                  border: 3,
                  borderColor: 'background.paper',
                  boxShadow: isActive ? `0 0 0 4px ${config.color}40` : 'none',
                  zIndex: 1,
                }}
              />

              {/* Session Card */}
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  borderLeft: 3,
                  borderColor: config.color,
                  bgcolor: isActive ? config.color + '08' : 'background.paper',
                }}
              >
                <Stack spacing={1.5}>
                  {/* Header */}
                  <Stack direction="row" alignItems="center" justifyContent="space-between">
                    <Stack direction="row" alignItems="center" spacing={1}>
                      <Box sx={{ color: config.color }}>{config.icon}</Box>
                      <Typography variant="subtitle2" fontWeight={600}>
                        {config.label}
                      </Typography>
                      {isActive && (
                        <Chip label="Active" size="small" color="success" variant="outlined" />
                      )}
                    </Stack>
                    <Typography variant="h6" fontWeight={700} color={config.color}>
                      {formatDuration(session.duration_minutes)}
                    </Typography>
                  </Stack>

                  {/* Time Range */}
                  <Stack direction="row" spacing={2} divider={<Divider orientation="vertical" flexItem />}>
                    <Box>
                      <Typography variant="caption" color="text.secondary" display="block">
                        Started
                      </Typography>
                      <Typography variant="body2" fontWeight={500}>
                        {formatDateTime(session.started_at)}
                      </Typography>
                    </Box>
                    {session.ended_at && (
                      <Box>
                        <Typography variant="caption" color="text.secondary" display="block">
                          Ended
                        </Typography>
                        <Typography variant="body2" fontWeight={500}>
                          {formatDateTime(session.ended_at)}
                        </Typography>
                      </Box>
                    )}
                  </Stack>

                  {/* Notes */}
                  {showNotes && (session.notes || session.paused_reason) && (
                    <>
                      <Divider />
                      <Box>
                        <Typography variant="caption" color="text.secondary" display="block" mb={0.5}>
                          Notes
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {session.notes || session.paused_reason}
                        </Typography>
                      </Box>
                    </>
                  )}
                </Stack>
              </Paper>
            </Box>
          );
        })}
      </Stack>
    </Box>
  );
}
