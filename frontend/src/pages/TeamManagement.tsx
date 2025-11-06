import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  IconButton,
  Alert,
  Snackbar,
  Grid,
  CircularProgress,
  Autocomplete,
  Tooltip,
} from '@mui/material'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import RefreshIcon from '@mui/icons-material/Refresh'
import LockResetIcon from '@mui/icons-material/LockReset'
import BarChartIcon from '@mui/icons-material/BarChart'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/services/api'
import type { TeamMember, Skill, TeamLevel } from '@/types'
import { useAuth } from '@/contexts/AuthContext'
import {
  useTeamMembers,
  useAddTeamMember,
  useUpdateTeamMember,
  useDeleteTeamMember,
} from '@/hooks/useTeam'
import { queryKeys } from '@/lib/queryClient'

interface RedmineUser {
  id: number
  name: string
  firstname?: string
  lastname?: string
  email: string
  login: string
  status: number
}

interface TeamMemberFormData {
  redmine_user_id: number
  name: string
  email: string
  team_level: TeamLevel
  max_tickets: number
  timezone: string
  work_start_hour: number
  work_end_hour: number
  skills: number[]
}

const initialFormData: TeamMemberFormData = {
  redmine_user_id: 0,
  name: '',
  email: '',
  team_level: 'L1' as TeamLevel,
  max_tickets: 8,
  timezone: 'Asia/Kolkata',
  work_start_hour: 9,
  work_end_hour: 18,
  skills: [],
}

export default function TeamManagement() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const {
    data: members = [],
    isLoading: membersLoading,
    isFetching: membersFetching,
    refetch: refetchMembers,
  } = useTeamMembers()
  const {
    data: skills = [],
    isLoading: skillsLoading,
  } = useQuery<Skill[]>({
    queryKey: queryKeys.team.skills(),
    queryFn: async () => apiClient.getSkills(),
    staleTime: 1000 * 60 * 10,
  })
  const addMemberMutation = useAddTeamMember()
  const updateMemberMutation = useUpdateTeamMember()
  const deleteMemberMutation = useDeleteTeamMember()
  const [redmineUsers, setRedmineUsers] = useState<RedmineUser[]>([])
  const [loadingRedmine, setLoadingRedmine] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingMember, setEditingMember] = useState<TeamMember | null>(null)
  const [formData, setFormData] = useState<TeamMemberFormData>(initialFormData)
  const [selectedRedmineUser, setSelectedRedmineUser] = useState<RedmineUser | null>(null)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })

  const isLoading = membersLoading || skillsLoading
  const isMembersRefreshing = membersFetching && !membersLoading

  // Password reset dialog state
  const [resetPasswordDialogOpen, setResetPasswordDialogOpen] = useState(false)
  const [resetMember, setResetMember] = useState<TeamMember | null>(null)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [resettingPassword, setResettingPassword] = useState(false)

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity })
  }

  const fetchRedmineUsers = async () => {
    try {
      setLoadingRedmine(true)
      const response = await fetch('/api/v1/redmine/group-members')
      const data = await response.json()
      if (data.success) {
        setRedmineUsers(data.members)
        showSnackbar(`Fetched ${data.count} users from Redmine`, 'success')
      }
    } catch (error) {
      console.error('Failed to fetch Redmine users:', error)
      showSnackbar('Failed to fetch Redmine users', 'error')
    } finally {
      setLoadingRedmine(false)
    }
  }

  const handleRedmineUserSelect = (user: RedmineUser | null) => {
    setSelectedRedmineUser(user)
    if (user) {
      setFormData({
        ...formData,
        redmine_user_id: user.id,
        name: user.name,
        email: user.email || '',
      })
    }
  }

  const handleOpenDialog = (member?: TeamMember) => {
    if (member) {
      setEditingMember(member)
      setFormData({
        redmine_user_id: member.redmine_user_id,
        name: member.name,
        email: member.email,
        team_level: member.team_level,
        max_tickets: member.max_tickets,
        timezone: member.timezone,
        work_start_hour: member.work_start_hour,
        work_end_hour: member.work_end_hour,
        skills: member.skills.map((s) => s.id),
      })
      setSelectedRedmineUser(null)
    } else {
      setEditingMember(null)
      setFormData(initialFormData)
      setSelectedRedmineUser(null)
      // Fetch Redmine users when creating new member
      if (redmineUsers.length === 0) {
        fetchRedmineUsers()
      }
    }
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingMember(null)
    setFormData(initialFormData)
  }

  const handleSubmit = async () => {
    try {
      if (editingMember) {
        await updateMemberMutation.mutateAsync({
          memberId: editingMember.id,
          updates: formData as any,
        })
        showSnackbar('Team member updated successfully', 'success')
      } else {
        await addMemberMutation.mutateAsync(formData as any)
        showSnackbar('Team member created successfully', 'success')
      }
      handleCloseDialog()
      await refetchMembers()
    } catch (error) {
      console.error('Failed to save team member:', error)
      showSnackbar('Failed to save team member', 'error')
    }
  }

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this team member?')) {
      return
    }

    try {
      await deleteMemberMutation.mutateAsync(id)
      showSnackbar('Team member deleted successfully', 'success')
      await refetchMembers()
    } catch (error) {
      console.error('Failed to delete team member:', error)
      showSnackbar('Failed to delete team member', 'error')
    }
  }

  const handleOpenResetPasswordDialog = (member: TeamMember) => {
    setResetMember(member)
    setNewPassword('')
    setConfirmPassword('')
    setResetPasswordDialogOpen(true)
  }

  const handleCloseResetPasswordDialog = () => {
    setResetPasswordDialogOpen(false)
    setResetMember(null)
    setNewPassword('')
    setConfirmPassword('')
  }

  const handleResetPassword = async () => {
    if (!resetMember || !resetMember.user_id) {
      showSnackbar('This team member is not linked to a user account', 'error')
      return
    }

    if (!newPassword || newPassword.length < 8) {
      showSnackbar('Password must be at least 8 characters long', 'error')
      return
    }

    if (newPassword !== confirmPassword) {
      showSnackbar('Passwords do not match', 'error')
      return
    }

    try {
      setResettingPassword(true)
      await apiClient.post(`/auth/users/${resetMember.user_id}/reset-password`, {
        new_password: newPassword,
        force_change: true
      })
      showSnackbar(`Password reset successfully for ${resetMember.name}`, 'success')
      handleCloseResetPasswordDialog()
    } catch (error: any) {
      console.error('Failed to reset password:', error)
      showSnackbar(error.response?.data?.detail || 'Failed to reset password', 'error')
    } finally {
      setResettingPassword(false)
    }
  }

  const handleViewPerformance = (memberId: number) => {
    navigate(`/team/performance/${memberId}`)
  }

  const columns: GridColDef[] = [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 150 },
    { field: 'email', headerName: 'Email', flex: 1, minWidth: 200 },
    {
      field: 'team_level',
      headerName: 'Level',
      width: 100,
      renderCell: (params: GridRenderCellParams) => (
        <Chip
          label={params.value}
          color={params.value === 'L1' ? 'success' : params.value === 'L2' ? 'primary' : 'secondary'}
          size="small"
        />
      ),
    },
    {
      field: 'skills',
      headerName: 'Skills',
      flex: 1,
      minWidth: 200,
      renderCell: (params: GridRenderCellParams) => (
        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
          {(params.value as Skill[] | undefined)?.slice(0, 3).map((skill: Skill) => (
            <Chip key={skill.id} label={skill.name} size="small" variant="outlined" />
          ))}
          {Array.isArray(params.value) && params.value.length > 3 && (
            <Chip label={`+${params.value.length - 3}`} size="small" variant="outlined" />
          )}
        </Box>
      ),
    },
    {
      field: 'current_load',
      headerName: 'Load',
      width: 150,
      renderCell: (params: GridRenderCellParams) => (
        <Box>
          <Typography variant="body2">
            {(params.row.current_tickets ?? 0)} / {params.row.max_tickets ?? 0}
          </Typography>
        </Box>
      ),
    },
    {
      field: 'sla_compliance_rate',
      headerName: 'SLA %',
      width: 100,
      renderCell: (params: GridRenderCellParams) => {
        const rate = Number(params.value ?? 0)
        const color =
          rate >= 90 ? 'success.main' : rate >= 70 ? 'warning.main' : 'error.main'

        return (
          <Typography variant="body2" color={color}>
            {rate.toFixed(1)}%
          </Typography>
        )
      },
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 200,
      sortable: false,
      renderCell: (params: GridRenderCellParams) => {
        const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'

        return (
          <Box display="flex" gap={0.5}>
            {isAdmin && (
              <Tooltip title="View Performance">
                <IconButton
                  size="small"
                  onClick={() => handleViewPerformance(params.row.id)}
                  color="info"
                >
                  <BarChartIcon />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Edit">
              <IconButton size="small" onClick={() => handleOpenDialog(params.row)} color="primary">
                <EditIcon />
              </IconButton>
            </Tooltip>
            {isAdmin && params.row.user_id && (
              <Tooltip title="Reset Password">
                <IconButton
                  size="small"
                  onClick={() => handleOpenResetPasswordDialog(params.row)}
                  color="warning"
                >
                  <LockResetIcon />
                </IconButton>
              </Tooltip>
            )}
            <Tooltip title="Delete">
              <IconButton size="small" onClick={() => handleDelete(params.row.id)} color="error">
                <DeleteIcon />
              </IconButton>
            </Tooltip>
          </Box>
        )
      },
    },
  ]

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Team Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
        >
          Add Team Member
        </Button>
      </Box>

      <Card>
        <CardContent>
          <DataGrid
            rows={members}
            columns={columns}
            initialState={{
              pagination: {
                paginationModel: { page: 0, pageSize: 10 },
              },
            }}
            pageSizeOptions={[10, 25, 50]}
            disableRowSelectionOnClick
            autoHeight
            loading={isMembersRefreshing}
          />
        </CardContent>
      </Card>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingMember ? 'Edit Team Member' : 'Add Team Member'}
        </DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            {/* Redmine User Selector (only for new members) */}
            {!editingMember && (
              <Grid item xs={12}>
                <Box display="flex" gap={1} alignItems="center">
                  <Autocomplete
                    fullWidth
                    options={redmineUsers}
                    getOptionLabel={(option) => `${option.name} (${option.email || option.login})`}
                    value={selectedRedmineUser}
                    onChange={(_, newValue) => handleRedmineUserSelect(newValue)}
                    loading={loadingRedmine}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Select Redmine User"
                        placeholder="Search for user from DevOps group"
                        helperText="Select a user from Redmine to auto-fill details"
                      />
                    )}
                    renderOption={(props, option) => (
                      <li {...props}>
                        <Box>
                          <Typography variant="body1">{option.name}</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {option.email || option.login} (ID: {option.id})
                          </Typography>
                        </Box>
                      </li>
                    )}
                  />
                  <IconButton
                    onClick={fetchRedmineUsers}
                    color="primary"
                    disabled={loadingRedmine}
                    title="Refresh Redmine users"
                  >
                    <RefreshIcon />
                  </IconButton>
                </Box>
              </Grid>
            )}

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                disabled={!!selectedRedmineUser}
                helperText={selectedRedmineUser ? "Auto-filled from Redmine" : ""}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                required
                disabled={!!selectedRedmineUser}
                helperText={selectedRedmineUser ? "Auto-filled from Redmine" : ""}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Redmine User ID"
                type="number"
                value={formData.redmine_user_id || ''}
                onChange={(e) => setFormData({ ...formData, redmine_user_id: parseInt(e.target.value) })}
                required
                disabled={!!selectedRedmineUser}
                helperText={selectedRedmineUser ? "Auto-filled from Redmine" : "Enter Redmine user ID"}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Team Level</InputLabel>
                <Select
                  value={formData.team_level}
                  label="Team Level"
                  onChange={(e) => setFormData({ ...formData, team_level: e.target.value as TeamLevel })}
                >
                  <MenuItem value="L1">L1</MenuItem>
                  <MenuItem value="L2">L2</MenuItem>
                  <MenuItem value="L3">L3</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Max Tickets"
                type="number"
                value={formData.max_tickets}
                onChange={(e) => setFormData({ ...formData, max_tickets: parseInt(e.target.value) })}
                inputProps={{ min: 1, max: 20 }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Timezone"
                value={formData.timezone}
                onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Work Start Hour (0-23)"
                type="number"
                value={formData.work_start_hour}
                onChange={(e) => setFormData({ ...formData, work_start_hour: parseInt(e.target.value) })}
                inputProps={{ min: 0, max: 23 }}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Work End Hour (0-23)"
                type="number"
                value={formData.work_end_hour}
                onChange={(e) => setFormData({ ...formData, work_end_hour: parseInt(e.target.value) })}
                inputProps={{ min: 0, max: 23 }}
              />
            </Grid>
            <Grid item xs={12}>
              <Autocomplete
                multiple
                options={skills}
                getOptionLabel={(option) => option.name}
                value={skills.filter((s) => formData.skills.includes(s.id))}
                onChange={(_, newValue) => {
                  setFormData({ ...formData, skills: newValue.map((s) => s.id) })
                }}
                renderInput={(params) => (
                  <TextField {...params} label="Skills" placeholder="Select skills" />
                )}
                renderTags={(value, getTagProps) =>
                  value.map((option, index) => (
                    <Chip label={option.name} {...getTagProps({ index })} />
                  ))
                }
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" color="primary">
            {editingMember ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Password Reset Dialog */}
      <Dialog open={resetPasswordDialogOpen} onClose={handleCloseResetPasswordDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" gap={1}>
            <LockResetIcon color="warning" />
            <Typography variant="h6">
              Reset Password for {resetMember?.name}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 3 }}>
            The user will be required to change this password on their next login.
          </Alert>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="New Password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                helperText="Password must be at least 8 characters long"
                disabled={resettingPassword}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Confirm Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                error={confirmPassword.length > 0 && newPassword !== confirmPassword}
                helperText={
                  confirmPassword.length > 0 && newPassword !== confirmPassword
                    ? 'Passwords do not match'
                    : ''
                }
                disabled={resettingPassword}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseResetPasswordDialog} disabled={resettingPassword}>
            Cancel
          </Button>
          <Button
            onClick={handleResetPassword}
            variant="contained"
            color="warning"
            disabled={resettingPassword || !newPassword || !confirmPassword}
            startIcon={resettingPassword ? <CircularProgress size={16} /> : <LockResetIcon />}
          >
            {resettingPassword ? 'Resetting...' : 'Reset Password'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  )
}
