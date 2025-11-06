import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Stack,
  Chip,
  Button,
  LinearProgress,
  Tooltip,
  IconButton,
  Alert,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import TimerIcon from '@mui/icons-material/Timer';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import type { ActiveWorkSession } from '@/types';

interface WorkSessionManagerProps {
  sessions: ActiveWorkSession[];
  maxSessions?: number;
  onPauseSession?: (ticketId: number) => void;
  onViewTicket?: (ticketId: number) => void;
  loading?: boolean;
  compact?: boolean;
}

const formatDuration = (minutes: number): string => {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
};

const calculateElapsedMinutes = (startedAt: string | null): number => {
  if (!startedAt) return 0;
  const start = new Date(startedAt);
  const now = new Date();
  return Math.floor((now.getTime() - start.getTime()) / 60000);
};

export default function WorkSessionManager({
  sessions,
  maxSessions = 2,
  onPauseSession,
  onViewTicket,
  loading = false,
  compact = false,
}: WorkSessionManagerProps) {
  const [liveDurations, setLiveDurations] = useState<Record<number, number>>({});

  // Update durations every minute
  useEffect(() => {
    const updateDurations = () => {
      const newDurations: Record<number, number> = {};
      sessions.forEach((session) => {
        if (session.is_running && session.started_at) {
          newDurations[session.session_id] = calculateElapsedMinutes(session.started_at);
        }
      });
      setLiveDurations(newDurations);
    };

    updateDurations();
    const interval = setInterval(updateDurations, 60000); // Update every minute

    return () => clearInterval(interval);
  }, [sessions]);

  const activeCount = sessions.filter((s) => s.is_running).length;
  const capacityPercent = (activeCount / maxSessions) * 100;

  if (compact) {
    return (
      <Card variant="outlined" sx={{ borderLeft: 4, borderColor: activeCount > 0 ? 'primary.main' : 'grey.400' }}>
        <CardContent>
          <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={2}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <TimerIcon color={activeCount > 0 ? 'primary' : 'disabled'} />
              <Typography variant="body2" fontWeight={600}>
                Active Work: {activeCount}/{maxSessions}
              </Typography>
            </Stack>
            {activeCount > 0 && (
              <Stack direction="row" spacing={1}>
                {sessions.slice(0, 2).map((session) => (
                  <Chip
                    key={session.session_id}
                    label={`#${session.ticket_redmine_id || session.ticket_id} • ${formatDuration(liveDurations[session.session_id] || session.duration_minutes)}`}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                ))}
              </Stack>
            )}
          </Stack>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          {/* Header */}
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              <TimerIcon color="primary" />
              <Typography variant="h6" fontWeight={600}>
                Active Work Sessions
              </Typography>
              <Tooltip title={`You can work on up to ${maxSessions} tickets simultaneously`}>
                <IconButton size="small">
                  <InfoOutlinedIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Stack>
            <Chip
              label={`${activeCount} / ${maxSessions}`}
              color={activeCount >= maxSessions ? 'error' : activeCount > 0 ? 'primary' : 'default'}
              size="small"
            />
          </Stack>

          {/* Capacity Bar */}
          <Box>
            <Stack direction="row" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="text.secondary">
                Work Capacity
              </Typography>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                {capacityPercent.toFixed(0)}%
              </Typography>
            </Stack>
            <LinearProgress
              variant="determinate"
              value={capacityPercent}
              color={capacityPercent >= 100 ? 'error' : 'primary'}
              sx={{ height: 8, borderRadius: 1 }}
            />
          </Box>

          {/* Loading State */}
          {loading && (
            <Box display="flex" justifyContent="center" py={2}>
              <LinearProgress sx={{ width: '100%' }} />
            </Box>
          )}

          {/* No Active Sessions */}
          {!loading && sessions.length === 0 && (
            <Alert severity="info" icon={<PlayArrowIcon />}>
              No active work sessions. Start working on a ticket to begin tracking time.
            </Alert>
          )}

          {/* Active Sessions List */}
          {!loading && sessions.length > 0 && (
            <Stack spacing={1.5}>
              {sessions.map((session) => {
                const elapsed = liveDurations[session.session_id] || session.duration_minutes;
                return (
                  <Card
                    key={session.session_id}
                    variant="outlined"
                    sx={{
                      borderLeft: 4,
                      borderColor: session.is_running ? 'success.main' : 'warning.main',
                      bgcolor: 'background.default',
                    }}
                  >
                    <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                      <Stack spacing={1}>
                        <Stack direction="row" alignItems="center" justifyContent="space-between">
                          <Stack direction="row" alignItems="center" spacing={1}>
                            <Chip
                              label={`#${session.ticket_redmine_id || session.ticket_id}`}
                              size="small"
                              color="primary"
                              variant="outlined"
                            />
                            {session.is_running && (
                              <Chip
                                icon={<PlayArrowIcon />}
                                label="Active"
                                size="small"
                                color="success"
                              />
                            )}
                          </Stack>
                          <Typography variant="body2" fontWeight={600} color="primary">
                            {formatDuration(elapsed)}
                          </Typography>
                        </Stack>

                        {session.ticket_subject && (
                          <Typography variant="body2" color="text.secondary" noWrap>
                            {session.ticket_subject}
                          </Typography>
                        )}

                        <Stack direction="row" spacing={1}>
                          {onViewTicket && (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => onViewTicket(session.ticket_id)}
                            >
                              View Details
                            </Button>
                          )}
                          {onPauseSession && session.is_running && (
                            <Button
                              size="small"
                              variant="outlined"
                              color="warning"
                              startIcon={<PauseIcon />}
                              onClick={() => onPauseSession(session.ticket_id)}
                            >
                              Pause
                            </Button>
                          )}
                        </Stack>
                      </Stack>
                    </CardContent>
                  </Card>
                );
              })}
            </Stack>
          )}

          {/* At Capacity Warning */}
          {activeCount >= maxSessions && (
            <Alert severity="warning">
              You have reached your maximum work capacity ({maxSessions} sessions).
              Pause a session before starting work on another ticket.
            </Alert>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
