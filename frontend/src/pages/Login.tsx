import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
  Container,
  Paper,
} from '@mui/material'
import {
  Visibility,
  VisibilityOff,
  Lock,
  Person,
  BusinessCenter,
} from '@mui/icons-material'
import { useAuth } from '../contexts/AuthContext'

export default function Login() {
  const navigate = useNavigate()
  const { login } = useAuth()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(username, password)
      navigate('/')  // Redirect to dashboard after successful login
    } catch (err: any) {
      console.error('Login error:', err)
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Login failed. Please check your credentials.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #7e8ba3 100%)',
        position: 'relative',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.05\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")',
          opacity: 0.3,
        },
      }}
    >
      <Container maxWidth="lg" sx={{ display: 'flex', alignItems: 'center', zIndex: 1 }}>
        <Box sx={{ width: '100%', display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
          {/* Left Panel - Branding */}
          <Box
            sx={{
              flex: 1,
              display: { xs: 'none', md: 'flex' },
              flexDirection: 'column',
              justifyContent: 'center',
              color: 'white',
              pr: 4,
            }}
          >
            <Box sx={{ mb: 4 }}>
              <BusinessCenter sx={{ fontSize: 72, mb: 2, opacity: 0.9 }} />
              <Typography variant="h3" fontWeight="700" gutterBottom sx={{ letterSpacing: '-0.5px' }}>
                DevOps Ticket Management
              </Typography>
              <Typography variant="h6" sx={{ opacity: 0.9, fontWeight: 300, lineHeight: 1.6 }}>
                Ticket tracking and SLA management system
              </Typography>
            </Box>
          </Box>

          {/* Right Panel - Login Card */}
          <Box sx={{ flex: { xs: 1, md: '0 0 480px' }, display: 'flex', alignItems: 'center' }}>
            <Paper
              elevation={24}
              sx={{
                width: '100%',
                borderRadius: 3,
                overflow: 'hidden',
                background: 'rgba(255, 255, 255, 0.98)',
                backdropFilter: 'blur(10px)',
              }}
            >
              <Box sx={{ bgcolor: 'primary.main', color: 'white', p: 3, textAlign: 'center' }}>
                <Lock sx={{ fontSize: 48, mb: 1 }} />
                <Typography variant="h5" fontWeight="600">
                  Secure Login
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.9, mt: 0.5 }}>
                  Sign in to access your dashboard
                </Typography>
              </Box>

              <CardContent sx={{ p: 4 }}>
                {/* Error Alert */}
                {error && (
                  <Alert severity="error" sx={{ mb: 3 }} variant="filled">
                    {error}
                  </Alert>
                )}

                {/* Login Form */}
                <form onSubmit={handleSubmit}>
                  <TextField
                    fullWidth
                    label="Username or Email"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    margin="normal"
                    required
                    autoFocus
                    disabled={loading}
                    variant="outlined"
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Person color="primary" />
                        </InputAdornment>
                      ),
                    }}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        '&:hover fieldset': {
                          borderColor: 'primary.main',
                        },
                      },
                    }}
                  />

                  <TextField
                    fullWidth
                    label="Password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    margin="normal"
                    required
                    disabled={loading}
                    variant="outlined"
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <Lock color="primary" />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <IconButton
                            onClick={() => setShowPassword(!showPassword)}
                            edge="end"
                            disabled={loading}
                          >
                            {showPassword ? <VisibilityOff /> : <Visibility />}
                          </IconButton>
                        </InputAdornment>
                      ),
                    }}
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        '&:hover fieldset': {
                          borderColor: 'primary.main',
                        },
                      },
                    }}
                  />

                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    size="large"
                    disabled={loading || !username || !password}
                    sx={{
                      mt: 4,
                      mb: 2,
                      py: 1.75,
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      textTransform: 'none',
                      boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                      '&:hover': {
                        boxShadow: '0 6px 16px rgba(0,0,0,0.2)',
                      },
                    }}
                  >
                    {loading ? (
                      <CircularProgress size={26} color="inherit" />
                    ) : (
                      'Sign In'
                    )}
                  </Button>
                </form>

                {/* Footer */}
                <Box sx={{ mt: 3, textAlign: 'center' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                    DevOps Ticket Management System v3.0.0
                  </Typography>
                  <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.5 }}>
                    Powered by Anthropic Claude
                  </Typography>
                </Box>
              </CardContent>
            </Paper>
          </Box>
        </Box>
      </Container>
    </Box>
  )
}
