import { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Chip,
  IconButton,
  CircularProgress,
  Divider,
  Tooltip,
} from '@mui/material';
import {
  AddCircle as AddCircleIcon,
  PersonAdd as PersonAddIcon,
  Edit as EditIcon,
  CheckCircle as CheckCircleIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Cancel as CancelIcon,
  Comment as CommentIcon,
  GroupAdd as GroupAddIcon,
  Person as PersonIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import apiClient from '@/services/api';

interface Activity {
  id: number;
  activity_type: string;
  title: string;
  description?: string;
  ticket_id?: number;
  user_id?: number;
  user_name?: string;
  metadata?: string;
  icon?: string;
  color?: string;
  created_at: string;
}

interface ActivityFeedProps {
  limit?: number;
  hours?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export default function ActivityFeed({
  limit = 20,
  hours = 24,
  autoRefresh = true,
  refreshInterval = 30000, // 30 seconds
}: ActivityFeedProps) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const statusStyleMap: Record<string, { icon: string; color: string; label: string }> = {
    new: { icon: 'add_circle', color: '#1976d2', label: 'New ticket created' },
    assigned: { icon: 'person_add', color: '#0288d1', label: 'Ticket assigned' },
    in_progress: { icon: 'trending_up', color: '#7b1fa2', label: 'Work in progress' },
    pending: { icon: 'warning', color: '#ef6c00', label: 'Waiting on customer' },
    resolved: { icon: 'check_circle', color: '#2e7d32', label: 'Ticket resolved' },
    closed: { icon: 'cancel', color: '#546e7a', label: 'Ticket closed' },
    breached: { icon: 'error', color: '#c62828', label: 'SLA breached' },
    escalated: { icon: 'group_add', color: '#ad1457', label: 'Escalated' },
  };

  const mapActivity = (item: any, index: number): Activity => {
    const statusRaw = (item.status || 'updated').toString();
    const statusKey = statusRaw.toLowerCase() as keyof typeof statusStyleMap;
    const style = statusStyleMap[statusKey] ?? { icon: 'info', color: '#757575', label: 'Ticket updated' };

    let ticketRef: number | undefined;
    for (const candidate of [item.redmine_ticket_id, item.ticket_id]) {
      if (typeof candidate === 'number' && Number.isFinite(candidate)) {
        ticketRef = candidate;
        break;
      }
      if (typeof candidate === 'string' && candidate.trim().length > 0) {
        const parsed = Number(candidate);
        if (Number.isFinite(parsed)) {
          ticketRef = parsed;
          break;
        }
      }
    }

    const titleParts: string[] = [];
    if (ticketRef) {
      titleParts.push(`#${ticketRef}`);
    }
    if (item.subject) {
      titleParts.push(item.subject);
    } else {
      titleParts.push(style.label);
    }

    const details: string[] = [];
    if (item.status) {
      details.push(`Status: ${statusRaw.replace(/_/g, ' ')}`);
    }
    if (item.assigned_to) {
      details.push(`Assignee: ${item.assigned_to}`);
    }

    const createdAt: string = item.updated_at ?? item.created_at ?? new Date().toISOString();

    let idSource: number;
    if (typeof item.id === 'number' && Number.isFinite(item.id)) {
      idSource = item.id;
    } else if (typeof ticketRef === 'number') {
      idSource = ticketRef * 1000 + index;
    } else {
      idSource = index;
    }

    return {
      id: idSource,
      activity_type: statusKey,
      title: titleParts.join(' · '),
      description: details.length ? details.join(' • ') : undefined,
      ticket_id: typeof ticketRef === 'number' ? ticketRef : undefined,
      user_name: item.assigned_to || undefined,
      metadata: statusRaw,
      icon: style.icon,
      color: style.color,
      created_at: createdAt,
    };
  };

  const fetchActivities = async () => {
    try {
      const response = await apiClient.getActivities(limit, hours);
      if (response.success) {
        const mapped = (response.activities ?? []).map(mapActivity);
        setActivities(mapped);
        setLastUpdate(new Date());
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();

    if (autoRefresh) {
      const interval = setInterval(fetchActivities, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [limit, hours, autoRefresh, refreshInterval]);

  const getIcon = (iconName: string, color: string) => {
    const iconMap: Record<string, JSX.Element> = {
      add_circle: <AddCircleIcon />,
      person_add: <PersonAddIcon />,
      edit: <EditIcon />,
      check_circle: <CheckCircleIcon />,
      trending_up: <TrendingUpIcon />,
      warning: <WarningIcon />,
      error: <ErrorIcon />,
      cancel: <CancelIcon />,
      comment: <CommentIcon />,
      group_add: <GroupAddIcon />,
      person: <PersonIcon />,
      info: <InfoIcon />,
    };

    const IconComponent = iconMap[iconName] || <InfoIcon />;

    return (
      <Avatar
        sx={{
          bgcolor: color || '#757575',
          width: 40,
          height: 40,
        }}
      >
        {IconComponent}
      </Avatar>
    );
  };

  const handleRefresh = () => {
    setLoading(true);
    fetchActivities();
  };

  if (loading && activities.length === 0) {
    return (
      <Card elevation={0} sx={{ border: '1px solid', borderColor: 'divider' }}>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      elevation={0}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <CardContent sx={{ pb: 1 }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6" fontWeight={600}>
            🔔 Live Activity Feed
          </Typography>
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="caption" color="text.secondary">
              Updated {formatDistanceToNow(lastUpdate, { addSuffix: true })}
            </Typography>
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={handleRefresh} disabled={loading}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {activities.length === 0 ? (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            minHeight={200}
            sx={{ opacity: 0.6 }}
          >
            <InfoIcon sx={{ fontSize: 48, mb: 2, color: 'text.secondary' }} />
            <Typography variant="body2" color="text.secondary">
              No recent activities
            </Typography>
          </Box>
        ) : (
          <List sx={{ maxHeight: 500, overflow: 'auto', pt: 0 }}>
            {activities.map((activity, index) => (
              <Box key={activity.id}>
                <ListItem
                  alignItems="flex-start"
                  sx={{
                    px: 2,
                    py: 1.5,
                    '&:hover': {
                      bgcolor: 'action.hover',
                      borderRadius: 1,
                    },
                    transition: 'all 0.2s ease',
                    animation: 'fadeIn 0.3s ease-in',
                    animationDelay: `${index * 50}ms`,
                    animationFillMode: 'backwards',
                    '@keyframes fadeIn': {
                      from: {
                        opacity: 0,
                        transform: 'translateY(10px)',
                      },
                      to: {
                        opacity: 1,
                        transform: 'translateY(0)',
                      },
                    },
                  }}
                >
                  <ListItemAvatar>
                    {getIcon(activity.icon || 'info', activity.color || '#757575')}
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
                        <Typography variant="body2" fontWeight={500}>
                          {activity.title}
                        </Typography>
                        {activity.ticket_id && (
                          <Chip
                            label={`#${activity.ticket_id}`}
                            size="small"
                            sx={{
                              height: 20,
                              fontSize: '0.7rem',
                              bgcolor: 'primary.main',
                              color: 'white',
                            }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Box>
                        {activity.description && (
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            display="block"
                            sx={{
                              mt: 0.5,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {activity.description}
                          </Typography>
                        )}
                        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                          {formatDistanceToNow(new Date(activity.created_at), { addSuffix: true })}
                          {activity.user_name && ` • by ${activity.user_name}`}
                        </Typography>
                      </Box>
                    }
                  />
                </ListItem>
                {index < activities.length - 1 && <Divider component="li" />}
              </Box>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
}
