import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Stack,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
  MenuItem,
  Select,
  LinearProgress,
  useTheme,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import WarningAmberIcon from '@mui/icons-material/WarningAmber'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import SearchIcon from '@mui/icons-material/Search'
import TimelineIcon from '@mui/icons-material/Timeline'
import TrendingDownIcon from '@mui/icons-material/TrendingDown'
import GroupIcon from '@mui/icons-material/Group'
import type { ProjectSummary } from '@/types'
import { useProjectSummaries } from '@/hooks/useProjects'
import { formatDistanceToNow } from 'date-fns'

const complianceColor = (rate: number) => {
  if (rate >= 95) return 'success'
  if (rate >= 85) return 'warning'
  return 'error'
}

export default function Projects() {
  const navigate = useNavigate()
  const theme = useTheme()
  const {
    data,
    isLoading,
    isFetching,
    refetch,
    error,
  } = useProjectSummaries()

  const [searchTerm, setSearchTerm] = useState('')
  const [slaFilter, setSlaFilter] = useState<'all' | 'atRisk' | 'healthy'>('all')
  const [sortKey, setSortKey] = useState<'activity' | 'sla' | 'open'>('activity')

  const projects = data?.projects ?? []

  const filteredProjects = useMemo(() => {
    const term = searchTerm.trim().toLowerCase()
    let result = projects

    if (term) {
      result = result.filter((project) =>
        project.project_jira_id.toLowerCase().includes(term)
      )
    }

    if (slaFilter === 'atRisk') {
      result = result.filter((project) => project.sla_compliance_rate < 90)
    } else if (slaFilter === 'healthy') {
      result = result.filter((project) => project.sla_compliance_rate >= 95)
    }

    result = [...result]

    result.sort((a, b) => {
      if (sortKey === 'sla') {
        return b.sla_compliance_rate - a.sla_compliance_rate
      }
      if (sortKey === 'open') {
        return b.open_tickets - a.open_tickets
      }

      const aActivity = a.last_activity ? new Date(a.last_activity).getTime() : 0
      const bActivity = b.last_activity ? new Date(b.last_activity).getTime() : 0
      return bActivity - aActivity
    })

    return result
  }, [projects, searchTerm, slaFilter, sortKey])

  const renderCard = (project: ProjectSummary) => {
    const lastActivityLabel = project.last_activity
      ? formatDistanceToNow(new Date(project.last_activity), { addSuffix: true })
      : 'No activity yet'

    const slaChipColor = complianceColor(project.sla_compliance_rate)
    const openTicketChipColor = project.open_tickets > 0 ? 'warning' : 'success'
    const breachesChipColor = project.breached_tickets > 0 ? 'error' : 'success'

    const slaProgress = Math.min(Math.max(project.sla_compliance_rate, 0), 100)
    const riskLevel = project.sla_compliance_rate < 85 || project.breached_tickets > 0
    const background = riskLevel
      ? `linear-gradient(135deg, ${theme.palette.error.light}33 0%, ${theme.palette.background.paper} 100%)`
      : `linear-gradient(135deg, ${theme.palette.primary.light}24 0%, ${theme.palette.background.paper} 100%)`

    return (
      <Grid item xs={12} md={6} lg={4} key={project.project_jira_id}>
        <Card
          variant="outlined"
          sx={{
            height: '100%',
            cursor: 'pointer',
            transition: 'all 0.2s ease-in-out',
            background,
            borderColor: riskLevel ? theme.palette.error.light : 'divider',
            '&:hover': { boxShadow: 8, transform: 'translateY(-4px)' },
          }}
          onClick={() => navigate(`/projects/${project.project_jira_id}`)}
        >
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
              <Typography variant="h6" fontWeight={600}>
                {project.project_jira_id}
              </Typography>
              <Stack direction="row" spacing={1}>
                <Chip
                  label={`${project.open_tickets} open`}
                  color={openTicketChipColor as any}
                  size="small"
                  icon={<WarningAmberIcon fontSize="small" />}
                />
                <Chip
                  label={`${project.breached_tickets} breaches`}
                  color={breachesChipColor as any}
                  size="small"
                  icon={<WarningAmberIcon fontSize="small" />}
                />
              </Stack>
            </Box>

              <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Total tickets:</strong> {project.total_tickets.toLocaleString()}
                </Typography>
                <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  label={`SLA ${project.sla_compliance_rate.toFixed(1)}%`}
                  color={slaChipColor as any}
                  size="small"
                  icon={<CheckCircleIcon fontSize="small" />}
                />
                <Chip
                  label={`${project.active_engineers} engineers`}
                  size="small"
                  icon={<GroupIcon fontSize="small" />}
                  variant="outlined"
                />
              </Stack>
                <Typography variant="caption" color="text.secondary">
                  Updated {lastActivityLabel}
                </Typography>
                <Box>
                  <LinearProgress
                    variant="determinate"
                    value={slaProgress}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      '& .MuiLinearProgress-bar': {
                        borderRadius: 3,
                      },
                    }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    SLA progress
                  </Typography>
                </Box>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
    )
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Box p={3}>
        <Alert severity="error">Failed to load projects.</Alert>
      </Box>
    )
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" fontWeight={700} gutterBottom>
            Projects
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Portfolio view of Jira projects managed by the automation platform
          </Typography>
        </Box>
        <Tooltip title="Refresh">
          <span>
            <IconButton
              onClick={() => refetch()}
              disabled={isFetching}
              size="small"
              sx={{ bgcolor: 'primary.main', color: 'white', '&:hover': { bgcolor: 'primary.dark' } }}
            >
              {isFetching ? <CircularProgress size={18} color="inherit" /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={5}>
              <TextField
                fullWidth
                placeholder="Search by Jira project ID"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={4}>
              <ToggleButtonGroup
                value={slaFilter}
                exclusive
                onChange={(_, value) => value && setSlaFilter(value)}
                size="small"
              >
                <ToggleButton value="all">All</ToggleButton>
                <ToggleButton value="atRisk">At Risk</ToggleButton>
                <ToggleButton value="healthy">Healthy</ToggleButton>
              </ToggleButtonGroup>
            </Grid>
            <Grid item xs={12} md={3}>
              <Select
                fullWidth
                size="small"
                value={sortKey}
                onChange={(event) => setSortKey(event.target.value as typeof sortKey)}
              >
                <MenuItem value="activity">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <TimelineIcon fontSize="small" />
                    <span>Recent activity</span>
                  </Stack>
                </MenuItem>
                <MenuItem value="sla">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CheckCircleIcon fontSize="small" />
                    <span>Highest SLA</span>
                  </Stack>
                </MenuItem>
                <MenuItem value="open">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <TrendingDownIcon fontSize="small" />
                    <span>Open tickets</span>
                  </Stack>
                </MenuItem>
              </Select>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {filteredProjects.length === 0 ? (
        <Alert severity="info">No projects with Jira IDs found yet.</Alert>
      ) : (
        <Grid container spacing={3}>
          {filteredProjects.map(renderCard)}
        </Grid>
      )}
    </Box>
  )
}
