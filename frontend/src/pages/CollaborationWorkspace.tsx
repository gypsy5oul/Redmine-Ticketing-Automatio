import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Paper,
  Avatar,
  Chip,
  Button,
  TextField,
  IconButton,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Autocomplete,
  Alert,
  Snackbar,
  CircularProgress,
  LinearProgress,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import PersonAddIcon from '@mui/icons-material/PersonAdd'
import SendIcon from '@mui/icons-material/Send'
import PersonRemoveIcon from '@mui/icons-material/PersonRemove'
import LaunchIcon from '@mui/icons-material/Launch'
import apiClient from '@/services/api'
import wsService, { WebSocketMessage } from '@/services/websocket'
import type { Ticket, Collaboration, CollaborationSummary, TeamMember } from '@/types'

interface CollaborationMessage {
  id: string
  member_name: string
  message: string
  timestamp: string
  type: 'message' | 'system'
}

export default function CollaborationWorkspace() {
  const { ticketId } = useParams<{ ticketId: string }>()
  const navigate = useNavigate()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [collaborators, setCollaborators] = useState<Collaboration[]>([])
  const [collaborationSummary, setCollaborationSummary] = useState<CollaborationSummary | null>(null)
  const [messages, setMessages] = useState<CollaborationMessage[]>([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [availableMembers, setAvailableMembers] = useState<TeamMember[]>([])
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null)
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as 'success' | 'error' })

  useEffect(() => {
    if (!localStorage.getItem('collab_user_name')) {
      localStorage.setItem('collab_user_name', 'Automation Agent')
    }
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchData = async () => {
    if (!ticketId) return

    try {
      setLoading(true)
      const [ticketData, collaborationSummaryData, membersData] = await Promise.all([
        apiClient.getTicket(parseInt(ticketId)),
        apiClient.getCollaborationSummary(parseInt(ticketId)),
        apiClient.getTeamMembers(),
      ])

      setTicket(ticketData)
      setCollaborationSummary(collaborationSummaryData)
      setCollaborators(collaborationSummaryData?.collaborators ?? [])
      setAvailableMembers(membersData)
    } catch (error) {
      console.error('Failed to fetch collaboration data:', error)
      showSnackbar('Failed to load collaboration data', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!ticketId) return

    fetchData()

    // Subscribe to WebSocket collaboration updates
    wsService.subscribeToCollaboration(parseInt(ticketId), (message: WebSocketMessage) => {
      console.log('Collaboration update:', message)

      if (message.type === 'collaboration_message') {
        const payload = (message.data ?? message) as { message?: string; member_name?: string; timestamp?: string }
        if (!payload?.message) {
          return
        }
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            member_name: payload.member_name || 'Automation Agent',
            message: payload.message || '',
            timestamp: payload.timestamp || message.timestamp || new Date().toISOString(),
            type: 'message',
          },
        ])
      } else if (message.type === 'collaboration_update') {
        fetchData()
      } else if (message.message) {
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now().toString(),
            member_name: 'Automation Agent',
            message: message.message || '',
            timestamp: message.timestamp || new Date().toISOString(),
            type: 'message',
          },
        ])
      }
    })

    return () => {
      wsService.unsubscribeFromCollaboration(parseInt(ticketId))
    }
  }, [ticketId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity })
  }

  const handleSendMessage = () => {
    if (!newMessage.trim() || !ticketId) return

    wsService.sendCollaborationMessage(parseInt(ticketId), newMessage)
    setNewMessage('')
  }

  const handleAddCollaborator = async () => {
    if (!selectedMember || !ticketId) return

    try {
      await apiClient.addCollaborator(parseInt(ticketId), {
        member_id: selectedMember.id,
        role: 'contributor',
      })
      showSnackbar('Collaborator added successfully', 'success')
      setAddDialogOpen(false)
      setSelectedMember(null)
      fetchData()
    } catch (error) {
      console.error('Failed to add collaborator:', error)
      showSnackbar('Failed to add collaborator', 'error')
    }
  }

  const handleRemoveCollaborator = async (memberId: number) => {
    if (!ticketId) return

    const confirmed = window.confirm('Remove this collaborator?')
    if (!confirmed) return

    try {
      await apiClient.removeCollaborator(parseInt(ticketId), memberId)
      showSnackbar('Collaborator removed successfully', 'success')
      fetchData()
    } catch (error) {
      console.error('Failed to remove collaborator:', error)
      showSnackbar('Failed to remove collaborator', 'error')
    }
  }

  if (loading || !ticket) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="80vh">
        <CircularProgress />
      </Box>
    )
  }

  const activeCollaborators = collaborators.filter((c) => c.is_active)
  const totalContribution = activeCollaborators.reduce((sum, c) => sum + (c.contribution_percentage || 0), 0)
  const ticketPriority = (ticket.priority || '').toString().toUpperCase()
  const statusLabel = (ticket.status || '').replace('_', ' ').toUpperCase()

  return (
    <Box>
      <Box display="flex" alignItems="center" gap={2} mb={3}>
        <IconButton onClick={() => navigate('/tickets')}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4">Collaboration Workspace</Typography>
      </Box>

      {/* Ticket Information */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="start">
            <Box>
              <Box display="flex" gap={1} alignItems="center" mb={1}>
                <Typography variant="h5">
                  Ticket #{ticket.redmine_ticket_id}: {ticket.subject}
                </Typography>
                <IconButton
                  size="small"
                  component="a"
                  href={ticket.redmine_url || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <LaunchIcon />
                </IconButton>
              </Box>
              <Box display="flex" gap={1} mb={2}>
                <Chip
                  label={ticket.priority}
                  color={ticketPriority.includes('P1') ? 'error' : ticketPriority.includes('P2') ? 'warning' : 'default'}
                  size="small"
                />
                <Chip label={statusLabel || 'STATUS'} size="small" />
                <Chip label={ticket.team_level || '—'} color="primary" size="small" />
              </Box>
          <Typography variant="body2" color="textSecondary">
            Assigned to: {ticket.assigned_to?.name || 'Unassigned'}
          </Typography>
          {collaborationSummary?.primary_assignee && (
            <Typography variant="body2" color="textSecondary">
              Primary Collaborator: {collaborationSummary.primary_assignee.name}
            </Typography>
          )}
        </Box>
        <Button
              variant="contained"
              startIcon={<PersonAddIcon />}
              onClick={() => setAddDialogOpen(true)}
            >
              Add Collaborator
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        {/* Collaborators Panel */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Active Collaborators ({activeCollaborators.length})
              </Typography>
              <List>
                {activeCollaborators.length === 0 && (
                  <ListItem>
                    <ListItemText
                      primary="No active collaborators yet."
                      primaryTypographyProps={{ variant: 'body2', color: 'textSecondary' }}
                    />
                  </ListItem>
                )}
                {activeCollaborators.map((collab) => (
                  <ListItem
                    key={collab.id}
                    secondaryAction={
                      <IconButton
                        edge="end"
                        onClick={() => handleRemoveCollaborator(collab.team_member_id)}
                        size="small"
                      >
                        <PersonRemoveIcon />
                      </IconButton>
                    }
                  >
                    <ListItemAvatar>
                      <Avatar>{collab.team_member?.name?.[0] || '?'}</Avatar>
                    </ListItemAvatar>
                    <ListItemText
                      primary={collab.team_member?.name || 'Team member'}
                      secondary={
                        <Box>
                          <Typography variant="caption" display="block">
                            {collab.role} • {collab.team_member?.team_level}
                          </Typography>
                          <Box mt={1}>
                            <Typography variant="caption">
                              Contribution: {(collab.contribution_percentage ?? 0).toFixed(1)}%
                            </Typography>
                            <LinearProgress
                              variant="determinate"
                              value={Math.min(100, Math.max(0, collab.contribution_percentage ?? 0))}
                              sx={{ mt: 0.5 }}
                            />
                          </Box>
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
                {activeCollaborators.length === 0 && (
                  <Typography variant="body2" color="textSecondary" sx={{ p: 2 }}>
                    No active collaborators yet. Add team members to collaborate on this ticket.
                  </Typography>
                )}
              </List>

              {collaborationSummary && (
                <Box mt={2} p={2} bgcolor="#f5f5f5" borderRadius={1}>
                  <Typography variant="subtitle2" color="textSecondary">
                    Total Contribution: {totalContribution.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Total Collaborators: {collaborationSummary.total_collaborators}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Total Time Logged: {(collaborationSummary.total_time_spent_hours ?? 0).toFixed(1)} hrs
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Total Comments: {collaborationSummary.total_comments ?? 0}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Ticket Description */}
          <Card sx={{ mt: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Description
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {ticket.description || 'No description available'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Chat Panel */}
        <Grid item xs={12} md={8}>
          <Card sx={{ height: 600, display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', p: 0 }}>
              <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
                <Typography variant="h6">Real-Time Collaboration Chat</Typography>
              </Box>

              {/* Messages */}
              <Box
                sx={{
                  flexGrow: 1,
                  p: 2,
                  overflowY: 'auto',
                  bgcolor: '#fafafa',
                }}
              >
                {messages.length === 0 ? (
                  <Box
                    display="flex"
                    justifyContent="center"
                    alignItems="center"
                    height="100%"
                  >
                    <Typography color="textSecondary">
                      No messages yet. Start the conversation!
                    </Typography>
                  </Box>
                ) : (
                  messages.map((msg) => (
                    <Box
                      key={msg.id}
                      sx={{
                        mb: 2,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: msg.type === 'system' ? 'center' : 'flex-start',
                      }}
                    >
                      {msg.type === 'system' ? (
                        <Chip label={msg.message} size="small" />
                      ) : (
                        <Paper
                          sx={{
                            p: 1.5,
                            maxWidth: '70%',
                            bgcolor: 'white',
                          }}
                        >
                          <Typography variant="caption" color="primary" fontWeight="bold">
                            {msg.member_name}
                          </Typography>
                          <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {msg.message}
                          </Typography>
                          <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5 }}>
                            {new Date(msg.timestamp).toLocaleTimeString()}
                          </Typography>
                        </Paper>
                      )}
                    </Box>
                  ))
                )}
                <div ref={messagesEndRef} />
              </Box>

              {/* Message Input */}
              <Box sx={{ p: 2, borderTop: '1px solid #e0e0e0' }}>
                <Box display="flex" gap={1}>
                  <TextField
                    fullWidth
                    placeholder="Type a message..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSendMessage()
                      }
                    }}
                    multiline
                    maxRows={3}
                  />
                  <IconButton
                    color="primary"
                    onClick={handleSendMessage}
                    disabled={!newMessage.trim()}
                  >
                    <SendIcon />
                  </IconButton>
                </Box>
              </Box>
            </CardContent>
          </Card>

          {/* WebSocket Status */}
          <Alert severity={wsService.isConnected() ? 'success' : 'warning'} sx={{ mt: 2 }}>
            {wsService.isConnected()
              ? 'Connected - Real-time updates enabled'
              : 'Disconnected - Trying to reconnect...'}
          </Alert>
        </Grid>
      </Grid>

      {/* Add Collaborator Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Collaborator</DialogTitle>
        <DialogContent>
          <Autocomplete
            options={availableMembers.filter(
              (m) => !activeCollaborators.some((c) => c.team_member_id === m.id)
            )}
            getOptionLabel={(option) => `${option.name} (${option.team_level})`}
            value={selectedMember}
            onChange={(_, newValue) => setSelectedMember(newValue)}
            renderInput={(params) => (
              <TextField {...params} label="Select Team Member" sx={{ mt: 2 }} />
            )}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleAddCollaborator}
            variant="contained"
            disabled={!selectedMember}
          >
            Add
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
