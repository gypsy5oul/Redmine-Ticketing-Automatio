import { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  Tooltip,
  CircularProgress,
  Button,
} from '@mui/material';
import type { Ticket, SLATracker } from '@/types';

interface KanbanTicket extends Ticket {
  sla_tracker?: SLATracker;
}

export interface KanbanColumn {
  id: string;
  title: string;
  accentColor: string;
  tickets: KanbanTicket[];
}

const formatMinutes = (minutes?: number | null): string => {
  if (!minutes || minutes <= 0) return '0m';
  const hours = Math.floor(minutes / 60);
  const remaining = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${remaining}m`;
  }
  return `${remaining}m`;
};

interface KanbanBoardProps {
  columns: KanbanColumn[];
  onCardDrop: (ticketId: number, targetColumnId: string) => void;
  loading?: boolean;
  onStartWork?: (ticketId: number) => void;
  onResumeWork?: (ticketId: number) => void;
  onPauseWork?: (ticketId: number) => void;
  workActionLoading?: boolean;
  canStartMoreWork?: boolean;
}

export default function KanbanBoard({
  columns,
  onCardDrop,
  loading = false,
  onStartWork,
  onResumeWork,
  onPauseWork,
  workActionLoading = false,
  canStartMoreWork = true,
}: KanbanBoardProps) {
  const [draggedTicketId, setDraggedTicketId] = useState<number | null>(null);
  const [activeColumn, setActiveColumn] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDragStart = (ticketId: number) => {
    setDraggedTicketId(ticketId);
    setIsDragging(true);
  };

  const handleDragEnd = () => {
    setDraggedTicketId(null);
    setActiveColumn(null);
    setIsDragging(false);
  };

  const handleDrop = (columnId: string) => {
    if (!draggedTicketId) return;
    onCardDrop(draggedTicketId, columnId);
    handleDragEnd();
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={320}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box display="grid" gridTemplateColumns={{ xs: '1fr', md: 'repeat(4, 1fr)' }} gap={2}>
      {columns.map((column) => {
        const isActive = activeColumn === column.id;
        const canDrop = isDragging && draggedTicketId !== null;
        return (
          <Paper
            key={column.id}
            variant={isActive ? 'elevation' : 'outlined'}
            elevation={isActive ? 8 : 1}
            sx={{
              minHeight: 320,
              bgcolor: isActive ? column.accentColor + '10' : 'background.default',
              borderColor: isActive ? column.accentColor : 'divider',
              borderWidth: isActive ? 3 : 1,
              borderStyle: isActive ? 'dashed' : 'solid',
              transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex',
              flexDirection: 'column',
              opacity: canDrop && !isActive ? 0.7 : 1,
              transform: isActive ? 'scale(1.02)' : 'scale(1)',
            }}
            onDragOver={(event) => {
              event.preventDefault();
              if (draggedTicketId) {
                setActiveColumn(column.id);
              }
            }}
            onDragLeave={() => {
              if (activeColumn === column.id) {
                setActiveColumn(null);
              }
            }}
            onDrop={(event) => {
              event.preventDefault();
              handleDrop(column.id);
            }}
          >
            <Box
              px={2}
              py={2}
              borderBottom="1px solid"
              borderColor="divider"
              display="flex"
              alignItems="center"
              justifyContent="space-between"
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    bgcolor: column.accentColor,
                  }}
                />
                <Typography variant="subtitle1" fontWeight={600}>
                  {column.title}
                </Typography>
              </Stack>
              <Chip
                label={column.tickets.length}
                size="small"
                sx={{
                  bgcolor: column.accentColor,
                  color: 'white',
                  fontWeight: 600,
                }}
              />
            </Box>

            <Box flex={1} overflow="auto" px={2} py={2}>
              {column.tickets.length === 0 ? (
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minHeight: 200,
                    border: isDragging ? `2px dashed ${column.accentColor}` : 'none',
                    borderRadius: 2,
                    bgcolor: isDragging ? column.accentColor + '08' : 'transparent',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <Typography variant="body2" color="text.secondary" textAlign="center" px={2}>
                    {isDragging ? `Drop here to move to ${column.title}` : `No tickets in ${column.title}`}
                  </Typography>
                </Box>
              ) : (
                column.tickets.map((ticket) => {
                  const isBeingDragged = draggedTicketId === ticket.id;
                const statusValue = (ticket.status || '').toString();
                const isTerminal = ['resolved', 'closed'].includes(statusValue);
                const activeSession = ticket.active_session;
                const hasActiveWork = activeSession?.type === 'active_work';
                const isWaiting = !!activeSession && !hasActiveWork && activeSession.type !== 'idle';
                const workMinutes = ticket.total_work_minutes ?? 0;
                const waitingMinutes = ticket.total_waiting_minutes ?? 0;
                const idleMinutes = ticket.total_idle_minutes ?? 0;

                return (
                  <Paper
                    key={ticket.id}
                    draggable
                    onDragStart={() => handleDragStart(ticket.id)}
                    onDragEnd={handleDragEnd}
                      sx={{
                        p: 2,
                        mb: 2,
                        cursor: 'grab',
                        borderLeft: `4px solid ${column.accentColor}`,
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                        opacity: isBeingDragged ? 0.5 : 1,
                        transform: isBeingDragged ? 'rotate(2deg)' : 'rotate(0deg)',
                        boxShadow: isBeingDragged ? 4 : 1,
                        '&:hover': {
                          boxShadow: 3,
                          transform: 'translateY(-2px)',
                        },
                        '&:active': {
                          cursor: 'grabbing',
                          transform: 'scale(0.98)',
                        },
                      }}
                    >

                    <Stack spacing={1}>
                      <Stack direction="row" alignItems="center" spacing={1} justifyContent="space-between">
                        <Typography variant="subtitle2" fontWeight={600}>
                          #{ticket.redmine_ticket_id} · {ticket.subject}
                        </Typography>
                        <Chip label={ticket.priority} size="small" color="warning" />
                      </Stack>
                      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Chip label={ticket.team_level} size="small" color="info" />
                        {ticket.assigned_to?.name && (
                          <Chip label={`Assigned: ${ticket.assigned_to.name}`} size="small" color="success" />
                        )}
                        {ticket.sla_tracker?.status && (
                          <Chip
                            label={`SLA: ${ticket.sla_tracker.status.replace('_', ' ')}`}
                            size="small"
                            color={
                              ticket.sla_tracker.status === 'critical'
                                ? 'error'
                                : ticket.sla_tracker.status === 'at_risk'
                                ? 'warning'
                                : 'default'
                            }
                          />
                        )}
                        {typeof ticket.sla_tracker?.time_remaining_minutes === 'number' && (
                          <Chip
                            label={`TTR: ${ticket.sla_tracker.time_remaining_minutes}m`}
                            size="small"
                            variant="outlined"
                          />
                        )}
                      </Stack>
                      <Stack direction="row" spacing={1} justifyContent="space-between">
                        <Typography variant="caption" color="text.secondary">
                          Created: {ticket.created_at ? new Date(ticket.created_at).toLocaleString() : 'Unknown'}
                        </Typography>
                        <Tooltip title="Drag to another stage to update status">
                          <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                            Drag to change status
                          </Typography>
                        </Tooltip>
                      </Stack>
                      <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                        <Chip
                          label={`Work ${formatMinutes(workMinutes)}`}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                        <Chip
                          label={`Wait ${formatMinutes(waitingMinutes)}`}
                          size="small"
                          color="warning"
                          variant="outlined"
                        />
                        <Chip label={`Idle ${formatMinutes(idleMinutes)}`} size="small" variant="outlined" />
                      </Stack>
                      {!isTerminal && (
                        <Stack direction="row" spacing={0.5}>
                          {hasActiveWork && onPauseWork && (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => onPauseWork(ticket.id)}
                              disabled={workActionLoading}
                            >
                              Pause
                            </Button>
                          )}
                          {isWaiting && onResumeWork && (
                            <Button
                              size="small"
                              variant="contained"
                              onClick={() => onResumeWork(ticket.id)}
                              disabled={workActionLoading}
                            >
                              Resume
                            </Button>
                          )}
                          {!hasActiveWork && !isWaiting && onStartWork && (
                            canStartMoreWork ? (
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => onStartWork(ticket.id)}
                                disabled={workActionLoading}
                              >
                                Start
                              </Button>
                            ) : (
                              <Tooltip title="You already have two active work sessions">
                                <span>
                                  <Button
                                    size="small"
                                    variant="contained"
                                    disabled
                                  >
                                    Start
                                  </Button>
                                </span>
                              </Tooltip>
                            )
                          )}
                        </Stack>
                      )}
                      {isTerminal && (
                        <Typography variant="caption" color="text.secondary">
                          Ticket resolved · Work {formatMinutes(workMinutes)}
                        </Typography>
                      )}
                    </Stack>
                  </Paper>
                  );
                })
              )}
            </Box>
          </Paper>
        );
      })}
    </Box>
  );
}
