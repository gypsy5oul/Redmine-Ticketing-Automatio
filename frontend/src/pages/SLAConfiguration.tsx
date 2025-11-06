import { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Switch,
  FormControlLabel,
  Button,
  Grid,
  Alert,
  Snackbar,
  CircularProgress,
  Divider,
  Chip,
} from '@mui/material'
import SaveIcon from '@mui/icons-material/Save'
import apiClient from '@/services/api'
import type { SLAPolicy } from '@/types'

interface SLAPolicyFormData {
  [key: string]: {
    response_time_minutes: number
    resolution_time_minutes: number
    escalation_time_minutes: number
    business_hours_only: boolean
  }
}

export default function SLAConfiguration() {
  const [policies, setPolicies] = useState<SLAPolicy[]>([])
  const [formData, setFormData] = useState<SLAPolicyFormData>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })

  const fetchPolicies = async () => {
    try {
      setLoading(true)
      const data = await apiClient.getSLAPolicies()
      setPolicies(data)

      // Initialize form data
      const initialFormData: SLAPolicyFormData = {}
      data.forEach((policy) => {
        initialFormData[policy.priority] = {
          response_time_minutes: policy.response_time_minutes,
          resolution_time_minutes: policy.resolution_time_minutes,
          escalation_time_minutes: policy.escalation_time_minutes,
          business_hours_only: policy.business_hours_only,
        }
      })
      setFormData(initialFormData)
    } catch (error) {
      console.error('Failed to fetch SLA policies:', error)
      showSnackbar('Failed to load SLA policies', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPolicies()
  }, [])

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity })
  }

  const handleChange = (priority: string, field: string, value: number | boolean) => {
    setFormData((prev) => ({
      ...prev,
      [priority]: {
        ...prev[priority],
        [field]: value,
      },
    }))
  }

  const handleSave = async (priority: string) => {
    try {
      setSaving(true)
      const policy = policies.find((p) => p.priority === priority)
      const changes = formData[priority]
      if (!policy || !changes) return

      await apiClient.updateSLAPolicy(policy.id, changes)
      showSnackbar(`SLA policy for ${priority} updated successfully`, 'success')
      fetchPolicies()
    } catch (error) {
      console.error('Failed to save SLA policy:', error)
      showSnackbar('Failed to save SLA policy', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveAll = async () => {
    try {
      setSaving(true)
      const updatePromises = policies.map((policy) =>
        formData[policy.priority]
          ? apiClient.updateSLAPolicy(policy.id, formData[policy.priority])
          : Promise.resolve(undefined)
      )
      await Promise.all(updatePromises)
      showSnackbar('All SLA policies updated successfully', 'success')
      fetchPolicies()
    } catch (error) {
      console.error('Failed to save SLA policies:', error)
      showSnackbar('Failed to save SLA policies', 'error')
    } finally {
      setSaving(false)
    }
  }

  const normalizePriorityKey = (priority: string) => {
    if (!priority) return 'P3'
    const match = priority.match(/(P[1-5])/i)
    return match ? match[1].toUpperCase() : priority.toUpperCase()
  }

  const getPriorityColor = (priority: string) => {
    const key = normalizePriorityKey(priority)
    switch (key) {
      case 'P1':
        return 'error'
      case 'P2':
        return 'warning'
      case 'P3':
        return 'info'
      case 'P4':
        return 'success'
      case 'P5':
        return 'default'
      default:
        return 'default'
    }
  }

  const formatTime = (minutes: number): string => {
    if (minutes < 60) {
      return `${minutes} minutes`
    }
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return mins > 0 ? `${hours}h ${mins}m` : `${hours} hours`
  }

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">SLA Configuration</Typography>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSaveAll}
          disabled={saving}
        >
          Save All Changes
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        Configure Service Level Agreement (SLA) policies for each priority level. Times are in minutes.
      </Alert>

      <Grid container spacing={3}>
        {policies.map((policy) => (
          <Grid item xs={12} key={policy.id}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Box display="flex" alignItems="center" gap={2}>
                    <Chip
                      label={policy.priority}
                      color={getPriorityColor(policy.priority)}
                      size="medium"
                    />
                    <Typography variant="h6">
                      {normalizePriorityKey(policy.priority) === 'P1' && 'Critical - Production Down'}
                      {normalizePriorityKey(policy.priority) === 'P2' && 'High - Major Impact'}
                      {normalizePriorityKey(policy.priority) === 'P3' && 'Medium - Moderate Impact'}
                      {normalizePriorityKey(policy.priority) === 'P4' && 'Low - Minor Impact'}
                      {normalizePriorityKey(policy.priority) === 'P5' && 'Very Low - Cosmetic'}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      Environment: {policy.environment ? policy.environment.toUpperCase() : 'ALL'}
                    </Typography>
                  </Box>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<SaveIcon />}
                    onClick={() => handleSave(policy.priority)}
                    disabled={saving}
                  >
                    Save
                  </Button>
                </Box>

                <Divider sx={{ mb: 2 }} />

                <Grid container spacing={3}>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      label="Response Time (minutes)"
                      type="number"
                      value={formData[policy.priority]?.response_time_minutes || 0}
                      onChange={(e) =>
                        handleChange(policy.priority, 'response_time_minutes', parseInt(e.target.value))
                      }
                      helperText={`Current: ${formatTime(formData[policy.priority]?.response_time_minutes || 0)}`}
                      inputProps={{ min: 1 }}
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      label="Resolution Time (minutes)"
                      type="number"
                      value={formData[policy.priority]?.resolution_time_minutes || 0}
                      onChange={(e) =>
                        handleChange(policy.priority, 'resolution_time_minutes', parseInt(e.target.value))
                      }
                      helperText={`Current: ${formatTime(formData[policy.priority]?.resolution_time_minutes || 0)}`}
                      inputProps={{ min: 1 }}
                    />
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <TextField
                      fullWidth
                      label="Auto-Escalation Time (minutes)"
                      type="number"
                      value={formData[policy.priority]?.escalation_time_minutes || 0}
                      onChange={(e) =>
                        handleChange(policy.priority, 'escalation_time_minutes', parseInt(e.target.value))
                      }
                      helperText={`Current: ${formatTime(formData[policy.priority]?.escalation_time_minutes || 0)}`}
                      inputProps={{ min: 1 }}
                    />
                  </Grid>
                </Grid>

                <Box mt={2}>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={formData[policy.priority]?.business_hours_only || false}
                        onChange={(e) =>
                          handleChange(policy.priority, 'business_hours_only', e.target.checked)
                        }
                      />
                    }
                    label="Count only business hours (9 AM - 6 PM weekdays)"
                  />
                </Box>

                <Box mt={2} p={2} bgcolor="#f5f5f5" borderRadius={1}>
                  <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                    Current SLA Times:
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="body2">
                        <strong>Response:</strong> {formatTime(policy.response_time_minutes)}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="body2">
                        <strong>Resolution:</strong> {formatTime(policy.resolution_time_minutes)}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="body2">
                        <strong>Escalation:</strong> {formatTime(policy.escalation_time_minutes)}
                      </Typography>
                    </Grid>
                  </Grid>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Recommended SLA Times Card */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recommended SLA Times (Industry Standard)
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="primary" gutterBottom>
                  P1 (Critical)
                </Typography>
                <Typography variant="body2">Response: 15-30 min | Resolution: 2-4 hours</Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="warning.main" gutterBottom>
                  P2 (High)
                </Typography>
                <Typography variant="body2">Response: 1-2 hours | Resolution: 8-12 hours</Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="info.main" gutterBottom>
                  P3 (Medium)
                </Typography>
                <Typography variant="body2">Response: 4-8 hours | Resolution: 24-48 hours</Typography>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Box>
                <Typography variant="subtitle2" color="success.main" gutterBottom>
                  P4/P5 (Low)
                </Typography>
                <Typography variant="body2">Response: 24 hours | Resolution: 3-7 days</Typography>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

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
