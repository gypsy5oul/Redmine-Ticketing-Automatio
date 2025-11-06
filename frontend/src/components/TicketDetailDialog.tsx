import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Box,
  Typography,
  Chip,
  Divider,
  Grid,
  Card,
  CardContent,
  Tab,
  Tabs,
  Stack,
  LinearProgress,
  Tooltip,
  Button,
  Paper,
} from '@mui/material';
import {
  Close as CloseIcon,
  Launch as LaunchIcon,
  Timeline as TimelineIcon,
  Comment as CommentIcon,
  Info as InfoIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  Person as PersonIcon,
  AccountCircle as AccountCircleIcon,
  Category as CategoryIcon,
  Speed as SpeedIcon,
  TrendingUp as TrendingUpIcon,
  AttachFile as AttachFileIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { apiClient } from '@/services/api';
import { Ticket, SLATracker, WorkSessionSummary, WorkSession, WorkSessionType } from '@/types';
import TicketComments from './TicketComments';

interface TicketDetailDialogProps {
  open: boolean;
  ticket: Ticket | null;
  onClose: () => void;
  onStartWork?: (ticketId: number) => Promise<void> | void;
  onResumeWork?: (ticketId: number) => Promise<void> | void;
  onPauseWork?: (ticketId: number) => void;
  workActionLoading?: boolean;
  canStartMoreWork?: boolean;
  onResolveTicket?: (ticketId: number) => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`ticket-tabpanel-${index}`}
      aria-labelledby={`ticket-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

const formatWorkMinutes = (minutes?: number | null): string => {
  if (!minutes || minutes <= 0) return '0m';
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${remaining}m`;
  }
  return `${remaining}m`;
};

const SESSION_LABELS: Record<WorkSessionType, string> = {
  active_work: 'Active Work',
  waiting_customer: 'Waiting · Customer',
  waiting_approval: 'Waiting · Approval',
  waiting_deployment: 'Waiting · Deployment',
  waiting_external: 'Waiting · External',
  idle: 'Idle',
};

const SESSION_CHIP_COLOR: Record<WorkSessionType, 'default' | 'primary' | 'warning' | 'success' | 'info' | 'secondary'> = {
  active_work: 'primary',
  waiting_customer: 'warning',
  waiting_approval: 'secondary',
  waiting_deployment: 'info',
  waiting_external: 'info',
  idle: 'default',
};

export const TicketDetailDialog: React.FC<TicketDetailDialogProps> = ({
  open,
  ticket,
  onClose,
  onStartWork,
  onResumeWork,
  onPauseWork,
  workActionLoading = false,
  canStartMoreWork = true,
  onResolveTicket,
}) => {
  const [tabValue, setTabValue] = useState(0);
  const [slaTracker, setSlaTracker] = useState<SLATracker | null>(null);
  const [loading, setLoading] = useState(false);
  const [workSummary, setWorkSummary] = useState<WorkSessionSummary | null>(null);
  const [workSummaryLoading, setWorkSummaryLoading] = useState(false);

  const ticketId = ticket?.id ?? null;

  const loadWorkSummary = useCallback(async () => {
    if (!ticketId) {
      setWorkSummary(null);
      return;
    }
    try {
      setWorkSummaryLoading(true);
      const summary = await apiClient.getWorkSummary(ticketId);
      setWorkSummary(summary);
    } catch (error) {
      console.error('Failed to load work summary:', error);
      setWorkSummary(null);
    } finally {
      setWorkSummaryLoading(false);
    }
  }, [ticketId]);

  const handleStartWorkClick = useCallback(async () => {
    if (!ticketId || !onStartWork) return;
    await Promise.resolve(onStartWork(ticketId));
    loadWorkSummary();
  }, [ticketId, onStartWork, loadWorkSummary]);

  const handleResumeWorkClick = useCallback(async () => {
    if (!ticketId || !onResumeWork) return;
    await Promise.resolve(onResumeWork(ticketId));
    loadWorkSummary();
  }, [ticketId, onResumeWork, loadWorkSummary]);

  const handlePauseWorkClick = useCallback(() => {
    if (!ticketId || !onPauseWork) return;
    onPauseWork(ticketId);
  }, [ticketId, onPauseWork]);

  useEffect(() => {
    if (ticket && open) {
      loadSLATracker();
      loadWorkSummary();
    } else if (!open) {
      setWorkSummary(null);
    }
  }, [ticket, open, loadWorkSummary]);

  const loadSLATracker = async () => {
    if (!ticket) return;

    try {
      setLoading(true);
      const sla = await apiClient.getSLAStatus(ticket.id);
      setSlaTracker(sla);
    } catch (error) {
      console.error('Failed to load SLA tracker:', error);
    } finally {
      setLoading(false);
    }
  };

  if (!ticket) return null;

  const getPriorityColor = (priority: string) => {
    const normalized = (priority || '').toUpperCase();
    if (normalized.includes('P1')) return '#d32f2f';
    if (normalized.includes('P2')) return '#f57c00';
    if (normalized.includes('P3')) return '#fbc02d';
    if (normalized.includes('P4')) return '#388e3c';
    return '#757575';
  };

  const getStatusColor = (status: string) => {
    const statusColors: Record<string, string> = {
      new: '#2196f3',
      assigned: '#9c27b0',
      in_progress: '#ff9800',
      resolved: '#4caf50',
      closed: '#757575',
      escalated: '#f44336',
    };
    return statusColors[status] || '#757575';
  };

  const getSLAColor = (status?: string) => {
    const statusColors: Record<string, string> = {
      within_sla: '#4caf50',
      at_risk: '#ff9800',
      critical: '#f44336',
      breached: '#d32f2f',
      met: '#4caf50',
    };
    return statusColors[status || ''] || '#757575';
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return format(new Date(dateString), 'MMM dd, yyyy • HH:mm');
  };

  const getSLAProgress = () => {
    return slaTracker?.completion_percentage || 0;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          maxHeight: '90vh',
        },
      }}
    >
      {/* Header */}
      <DialogTitle
        sx={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
          py: 2.5,
          px: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Box display="flex" alignItems="center" gap={2} flex={1}>
          <Box
            sx={{
              bgcolor: 'rgba(255, 255, 255, 0.2)',
              borderRadius: 2,
              p: 1,
              display: 'flex',
            }}
          >
            <InfoIcon sx={{ fontSize: 28 }} />
          </Box>
          <Box flex={1}>
            <Typography variant="h6" fontWeight={600}>
              Ticket #{ticket.redmine_ticket_id}
            </Typography>
            <Typography variant="body2" sx={{ opacity: 0.9 }}>
              {ticket.subject}
            </Typography>
          </Box>
        </Box>

        <Stack direction="row" spacing={1}>
          {ticket.redmine_url && (
            <Tooltip title="Open in Redmine">
              <IconButton
                sx={{ color: 'white' }}
                onClick={() => window.open(ticket.redmine_url, '_blank')}
              >
                <LaunchIcon />
              </IconButton>
            </Tooltip>
          )}
          <IconButton sx={{ color: 'white' }} onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Stack>
      </DialogTitle>

      {loading && <LinearProgress />}

      <DialogContent sx={{ p: 0 }}>
        {/* Status Banner */}
        <Box
          sx={{
            bgcolor: 'grey.50',
            borderBottom: '1px solid',
            borderColor: 'grey.200',
            px: 3,
            py: 2,
          }}
        >
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  PRIORITY
                </Typography>
                <Chip
                  label={ticket.priority}
                  size="small"
                  sx={{
                    bgcolor: getPriorityColor(ticket.priority as string),
                    color: 'white',
                    fontWeight: 600,
                    width: 'fit-content',
                  }}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  STATUS
                </Typography>
                <Chip
                  label={ticket.status.replace('_', ' ').toUpperCase()}
                  size="small"
                  sx={{
                    bgcolor: getStatusColor(ticket.status),
                    color: 'white',
                    fontWeight: 600,
                    width: 'fit-content',
                  }}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  TEAM LEVEL
                </Typography>
                <Chip
                  label={ticket.team_level}
                  size="small"
                  sx={{
                    bgcolor: 'primary.main',
                    color: 'white',
                    fontWeight: 600,
                    width: 'fit-content',
                  }}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={3}>
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary" fontWeight={600}>
                  SLA STATUS
                </Typography>
                <Chip
                  label={slaTracker?.status?.replace('_', ' ').toUpperCase() || 'N/A'}
                  size="small"
                  sx={{
                    bgcolor: getSLAColor(slaTracker?.status),
                    color: 'white',
                    fontWeight: 600,
                    width: 'fit-content',
                  }}
                />
              </Stack>
            </Grid>
          </Grid>
        </Box>

        {/* Tabs */}
        <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3 }}>
          <Tabs value={tabValue} onChange={(_, newValue) => setTabValue(newValue)}>
            <Tab icon={<InfoIcon />} iconPosition="start" label="Details" />
            <Tab icon={<ScheduleIcon />} iconPosition="start" label="Work Tracking" />
            <Tab icon={<CommentIcon />} iconPosition="start" label="Comments" />
            <Tab icon={<TimelineIcon />} iconPosition="start" label="Timeline" />
          </Tabs>
        </Box>

        {/* Tab Panels */}
        <Box sx={{ px: 3, pb: 3 }}>
          {/* Details Tab */}
          <TabPanel value={tabValue} index={0}>
            <Grid container spacing={3}>
              {/* Left Column */}
              <Grid item xs={12} md={8}>
                <Card
                  elevation={0}
                  sx={{
                    border: '1px solid',
                    borderColor: 'grey.200',
                    borderRadius: 2,
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Typography variant="h6" fontWeight={600} gutterBottom>
                      Description
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        lineHeight: 1.8,
                        mt: 2,
                      }}
                    >
                      {ticket.description || 'No description available'}
                    </Typography>
                  </CardContent>
                </Card>

                {/* Attachments */}
                {ticket.attachments && ticket.attachments.length > 0 && (
                  <Card
                    elevation={0}
                    sx={{
                      border: '1px solid',
                      borderColor: 'grey.200',
                      borderRadius: 2,
                      mt: 3,
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Box display="flex" alignItems="center" gap={1} mb={2}>
                        <AttachFileIcon color="action" />
                        <Typography variant="h6" fontWeight={600}>
                          Attachments ({ticket.attachments.length})
                        </Typography>
                      </Box>
                      <Stack spacing={1.5}>
                        {ticket.attachments.map((attachment) => (
                          <Paper
                            key={attachment.id}
                            elevation={0}
                            sx={{
                              p: 2,
                              border: '1px solid',
                              borderColor: 'grey.300',
                              borderRadius: 1,
                              '&:hover': {
                                bgcolor: 'grey.50',
                                borderColor: 'primary.main',
                              },
                            }}
                          >
                            <Box display="flex" alignItems="center" justifyContent="space-between">
                              <Box display="flex" alignItems="center" gap={1.5} flex={1}>
                                <AttachFileIcon fontSize="small" color="action" />
                                <Box>
                                  <Typography variant="body2" fontWeight={500}>
                                    {attachment.filename}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary">
                                    {(attachment.filesize / 1024).toFixed(2)} KB
                                    {attachment.description && ` • ${attachment.description}`}
                                  </Typography>
                                </Box>
                              </Box>
                              <Tooltip title="Download attachment">
                                <IconButton
                                  size="small"
                                  color="primary"
                                  component="a"
                                  href={attachment.content_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  <DownloadIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          </Paper>
                        ))}
                      </Stack>
                    </CardContent>
                  </Card>
                )}

                {/* SLA Progress */}
                {slaTracker && (
                  <Card
                    elevation={0}
                    sx={{
                      border: '1px solid',
                      borderColor: 'grey.200',
                      borderRadius: 2,
                      mt: 3,
                    }}
                  >
                    <CardContent sx={{ p: 3 }}>
                      <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                        <Typography variant="h6" fontWeight={600}>
                          SLA Progress
                        </Typography>
                        <Chip
                          label={`${getSLAProgress()}%`}
                          size="small"
                          sx={{
                            bgcolor: getSLAColor(slaTracker.status),
                            color: 'white',
                            fontWeight: 600,
                          }}
                        />
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={getSLAProgress()}
                        sx={{
                          height: 10,
                          borderRadius: 5,
                          bgcolor: 'grey.200',
                          '& .MuiLinearProgress-bar': {
                            bgcolor: getSLAColor(slaTracker.status),
                            borderRadius: 5,
                          },
                        }}
                      />
                      <Box display="flex" justifyContent="space-between" mt={2}>
                        <Typography variant="caption" color="text.secondary">
                          Time Remaining: {slaTracker.time_remaining_minutes || 0} minutes
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Deadline: {formatDate(slaTracker.resolution_deadline)}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                )}
              </Grid>

              {/* Right Column - Metadata */}
              <Grid item xs={12} md={4}>
                <Card
                  elevation={0}
                  sx={{
                    border: '1px solid',
                    borderColor: 'grey.200',
                    borderRadius: 2,
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Typography variant="h6" fontWeight={600} gutterBottom>
                      Information
                    </Typography>

                    <Stack spacing={2.5} mt={2}>
                      {/* Requester */}
                      <Box>
                        <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                          <AccountCircleIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                          <Typography variant="caption" color="text.secondary" fontWeight={600}>
                            RAISED BY
                          </Typography>
                        </Box>
                        <Typography variant="body2" fontWeight={500}>
                          {ticket.requester_name || 'Customer'}
                        </Typography>
                      </Box>

                      {/* Assigned To */}
                      <Box>
                        <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                          <PersonIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                          <Typography variant="caption" color="text.secondary" fontWeight={600}>
                            ASSIGNED TO
                          </Typography>
                        </Box>
                        <Typography variant="body2" fontWeight={500}>
                          {ticket.assigned_to?.name || 'Unassigned'}
                        </Typography>
                      </Box>

                      {/* Category */}
                      {ticket.category && (
                        <Box>
                          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                            <CategoryIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                              CATEGORY
                            </Typography>
                          </Box>
                          <Chip
                            label={ticket.category}
                            size="small"
                            sx={{ textTransform: 'capitalize' }}
                          />
                        </Box>
                      )}

                      {/* Complexity */}
                      {ticket.complexity && (
                        <Box>
                          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                            <SpeedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                              COMPLEXITY
                            </Typography>
                          </Box>
                          <Chip
                            label={ticket.complexity}
                            size="small"
                            color={
                              ticket.complexity === 'critical'
                                ? 'error'
                                : ticket.complexity === 'complex'
                                ? 'warning'
                                : 'success'
                            }
                            sx={{ textTransform: 'capitalize' }}
                          />
                        </Box>
                      )}

                      {/* Estimated Resolution */}
                      {ticket.estimated_resolution_hours && (
                        <Box>
                          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                            <TrendingUpIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                              ESTIMATED RESOLUTION
                            </Typography>
                          </Box>
                          <Typography variant="body2" fontWeight={500}>
                            {ticket.estimated_resolution_hours.toFixed(1)} hours
                          </Typography>
                      </Box>
                    )}

                      {ticket.resolution_notes && (
                        <Box>
                          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                            <HistoryIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                              RESOLUTION NOTES
                            </Typography>
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                            {ticket.resolution_notes}
                          </Typography>
                        </Box>
                      )}

                      <Divider />

                      {/* Timestamps */}
                      <Box>
                        <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                          <ScheduleIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                          <Typography variant="caption" color="text.secondary" fontWeight={600}>
                            CREATED
                          </Typography>
                        </Box>
                        <Typography variant="body2">{formatDate(ticket.created_at)}</Typography>
                      </Box>

                      {ticket.assigned_at && (
                        <Box>
                          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                            <ScheduleIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                              ASSIGNED
                            </Typography>
                          </Box>
                          <Typography variant="body2">{formatDate(ticket.assigned_at)}</Typography>
                        </Box>
                      )}
                    </Stack>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </TabPanel>

          {/* Work Tracking Tab */}
          <TabPanel value={tabValue} index={1}>
            {workSummaryLoading ? (
              <LinearProgress />
            ) : workSummary ? (
              <Stack spacing={2}>
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  spacing={1}
                  justifyContent="space-between"
                  alignItems={{ xs: 'flex-start', md: 'center' }}
                >
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    <Chip label={`Work ${formatWorkMinutes(workSummary.total_work_minutes)}`} size="small" color="primary" variant="outlined" />
                    <Chip label={`Wait ${formatWorkMinutes(workSummary.total_waiting_minutes)}`} size="small" color="warning" variant="outlined" />
                    <Chip label={`Idle ${formatWorkMinutes(workSummary.total_idle_minutes)}`} size="small" variant="outlined" />
                    {typeof workSummary.work_efficiency_percent === 'number' && (
                      <Chip
                        label={`Efficiency ${Math.round(workSummary.work_efficiency_percent)}%`}
                        size="small"
                        color="success"
                        variant="outlined"
                      />
                    )}
                  </Stack>
                  {ticket.resolution_notes && (
                    <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 360, textAlign: 'right' }}>
                      Resolution notes saved – see the Details tab for full context.
                    </Typography>
                  )}
                  {ticket && (
                    <Stack direction="row" spacing={1}>
                      {(() => {
                        const statusValue = (ticket.status || '').toString();
                        const isTerminal = ['resolved', 'closed'].includes(statusValue);
                        const activeSession = workSummary.active_session || ticket.active_session || null;
                        const hasActiveWork = activeSession?.type === 'active_work';
                        const isWaiting = !!activeSession && !hasActiveWork && activeSession.type !== 'idle';

                        if (isTerminal) {
                          return <Chip label="Ticket resolved" size="small" />;
                        }

                        if (hasActiveWork) {
                          return (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={handlePauseWorkClick}
                              disabled={workActionLoading}
                            >
                              Pause
                            </Button>
                          );
                        }

                        if (isWaiting) {
                          return (
                            <Button
                              size="small"
                              variant="contained"
                              onClick={handleResumeWorkClick}
                              disabled={workActionLoading}
                            >
                              Resume
                            </Button>
                          );
                        }

                        if (onStartWork) {
                          if (canStartMoreWork) {
                            return (
                              <Button
                                size="small"
                                variant="contained"
                                onClick={handleStartWorkClick}
                                disabled={workActionLoading}
                              >
                                Start Work
                              </Button>
                            );
                          }
                          return (
                            <Tooltip title="You already have two active work sessions">
                              <span>
                                <Button size="small" variant="contained" disabled>
                                  Start Work
                                </Button>
                              </span>
                            </Tooltip>
                          );
                        }

                        return null;
                      })()}
                      {(() => {
                        const statusValue = (ticket.status || '').toString();
                        const isTerminal = ['resolved', 'closed'].includes(statusValue);
                        if (isTerminal || !onResolveTicket) return null;
                        return (
                          <Button
                            size="small"
                            variant="text"
                            onClick={() => onResolveTicket(ticket.id)}
                            disabled={workActionLoading}
                          >
                            Resolve
                          </Button>
                        );
                      })()}
                    </Stack>
                  )}
                </Stack>

                {workSummary.active_session && (
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip label="Active" color="success" size="small" />
                    <Typography variant="body2" color="text.secondary">
                      Active session started {workSummary.active_session.started_at ? format(new Date(workSummary.active_session.started_at), 'MMM dd • HH:mm') : 'recently'}
                    </Typography>
                  </Box>
                )}

                {workSummary.work_sessions.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No work sessions recorded yet. Start work on this ticket to begin tracking time.
                  </Typography>
                ) : (
                  <Stack spacing={1.5}>
                    {workSummary.work_sessions.map((session: WorkSession) => (
                      <Paper
                        key={session.id}
                        variant="outlined"
                        sx={{
                          p: 2,
                          borderColor: session.is_active ? 'primary.main' : 'divider',
                          borderWidth: session.is_active ? 2 : 1,
                        }}
                      >
                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} justifyContent="space-between">
                          <Stack spacing={0.5}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Chip
                                label={SESSION_LABELS[session.type as WorkSessionType] || session.type}
                                color={SESSION_CHIP_COLOR[session.type as WorkSessionType] ?? 'default'}
                                size="small"
                              />
                              {session.is_active && <Chip label="Active" size="small" color="success" variant="outlined" />}
                            </Stack>
                            <Typography variant="body2" color="text.secondary">
                              {session.started_at ? format(new Date(session.started_at), 'MMM dd, yyyy • HH:mm') : 'Unknown start'}
                              {' → '}
                              {session.ended_at
                                ? format(new Date(session.ended_at), 'MMM dd, yyyy • HH:mm')
                                : session.is_active
                                ? 'In progress'
                                : 'Unknown end'}
                            </Typography>
                          </Stack>
                          <Typography variant="subtitle2" fontWeight={600}>
                            {formatWorkMinutes(session.duration_minutes)}
                          </Typography>
                        </Stack>
                        {session.notes && (
                          <Typography variant="body2" sx={{ mt: 1 }}>
                            {session.notes}
                          </Typography>
                        )}
                        {session.paused_reason && session.type !== 'active_work' && (
                          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                            Reason: {session.paused_reason}
                          </Typography>
                        )}
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Work session data unavailable. This ticket may not have been picked up yet.
              </Typography>
            )}
          </TabPanel>

          {/* Comments Tab */}
          <TabPanel value={tabValue} index={2}>
            <TicketComments ticketId={ticket.id} currentUserId={ticket.assigned_to_id || 1} />
          </TabPanel>

          {/* Timeline Tab */}
          <TabPanel value={tabValue} index={3}>
            <Card
              elevation={0}
              sx={{
                border: '1px solid',
                borderColor: 'grey.200',
                borderRadius: 2,
                p: 3,
                textAlign: 'center',
              }}
            >
              <HistoryIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
              <Typography variant="body1" color="text.secondary">
                Timeline feature coming soon!
              </Typography>
            </Card>
          </TabPanel>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default TicketDetailDialog;
