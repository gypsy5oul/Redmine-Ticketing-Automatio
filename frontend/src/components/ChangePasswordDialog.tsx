import { useState } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Alert,
  IconButton,
  InputAdornment,
} from '@mui/material'
import { Visibility, VisibilityOff } from '@mui/icons-material'
import { apiClient } from '../services/api'

interface ChangePasswordDialogProps {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
  required?: boolean
}

export default function ChangePasswordDialog({
  open,
  onClose,
  onSuccess,
  required = false,
}: ChangePasswordDialogProps) {
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showOldPassword, setShowOldPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    setError('')

    // Validation
    if (!oldPassword || !newPassword || !confirmPassword) {
      setError('All fields are required')
      return
    }

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters long')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match')
      return
    }

    if (oldPassword === newPassword) {
      setError('New password must be different from old password')
      return
    }

    setLoading(true)

    try {
      await apiClient.client.post('/api/v1/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword,
      })

      // Clear form
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')

      // Call success callback
      if (onSuccess) {
        onSuccess()
      }

      // Close dialog
      onClose()
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          'Failed to change password. Please check your current password and try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    if (required) {
      setError('You must change your password before continuing')
      return
    }
    onClose()
  }

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      disableEscapeKeyDown={required}
    >
      <DialogTitle>
        {required ? 'Password Change Required' : 'Change Password'}
      </DialogTitle>
      <DialogContent>
        {required && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            For security reasons, you must change your password before continuing.
          </Alert>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <TextField
          fullWidth
          label="Current Password"
          type={showOldPassword ? 'text' : 'password'}
          value={oldPassword}
          onChange={(e) => setOldPassword(e.target.value)}
          margin="normal"
          required
          disabled={loading}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={() => setShowOldPassword(!showOldPassword)}
                  edge="end"
                >
                  {showOldPassword ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        <TextField
          fullWidth
          label="New Password"
          type={showNewPassword ? 'text' : 'password'}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          margin="normal"
          required
          disabled={loading}
          helperText="Must be at least 8 characters long"
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  edge="end"
                >
                  {showNewPassword ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        <TextField
          fullWidth
          label="Confirm New Password"
          type={showConfirmPassword ? 'text' : 'password'}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          margin="normal"
          required
          disabled={loading}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  edge="end"
                >
                  {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
      </DialogContent>
      <DialogActions>
        {!required && (
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
        )}
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={loading}
        >
          {loading ? 'Changing...' : 'Change Password'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
