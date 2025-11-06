import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Avatar,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  ToggleButtonGroup,
  ToggleButton,
  Divider,
  Stack,
  Paper,
  Tooltip,
  Fade,
  Zoom,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Comment as CommentIcon,
  Public as PublicIcon,
  Lock as LockIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Send as SendIcon,
  Close as CloseIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { apiClient } from '@/services/api';
import { TicketComment, CommentType } from '@/types';

interface TicketCommentsProps {
  ticketId: number;
  currentUserId: number;
}

export const TicketComments: React.FC<TicketCommentsProps> = ({ ticketId, currentUserId }) => {
  const [comments, setComments] = useState<TicketComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState('');
  const [commentType, setCommentType] = useState<CommentType>(CommentType.PUBLIC);
  const [editingComment, setEditingComment] = useState<number | null>(null);
  const [editContent, setEditContent] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [commentToDelete, setCommentToDelete] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    loadComments();
  }, [ticketId]);

  const loadComments = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getTicketComments(ticketId);
      setComments(data.comments);
    } catch (error) {
      console.error('Failed to load comments:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitComment = async () => {
    if (!newComment.trim()) return;

    try {
      setSubmitting(true);
      await apiClient.createComment(ticketId, newComment.trim(), currentUserId, commentType);
      setNewComment('');
      setSuccessMessage('Comment added successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
      await loadComments();
    } catch (error) {
      console.error('Failed to create comment:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartEdit = (comment: TicketComment) => {
    setEditingComment(comment.id);
    setEditContent(comment.content);
  };

  const handleSaveEdit = async () => {
    if (!editingComment || !editContent.trim()) return;

    try {
      await apiClient.updateComment(editingComment, editContent.trim());
      setEditingComment(null);
      setEditContent('');
      setSuccessMessage('Comment updated successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
      await loadComments();
    } catch (error) {
      console.error('Failed to update comment:', error);
    }
  };

  const handleDeleteClick = (commentId: number) => {
    setCommentToDelete(commentId);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!commentToDelete) return;

    try {
      await apiClient.deleteComment(commentToDelete);
      setDeleteDialogOpen(false);
      setCommentToDelete(null);
      setSuccessMessage('Comment deleted successfully!');
      setTimeout(() => setSuccessMessage(''), 3000);
      await loadComments();
    } catch (error) {
      console.error('Failed to delete comment:', error);
    }
  };

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'MMM dd, yyyy • HH:mm');
  };

  const getInitials = (name: string | null) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getAvatarColor = (name: string | null) => {
    if (!name) return '#9e9e9e';
    const colors = [
      '#1976d2', '#2e7d32', '#d32f2f', '#7b1fa2',
      '#f57c00', '#0288d1', '#c62828', '#5e35b1',
    ];
    const hash = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ mt: 3 }}>
      {/* Success Message */}
      {successMessage && (
        <Zoom in>
          <Alert
            severity="success"
            icon={<CheckCircleIcon />}
            sx={{ mb: 2 }}
            onClose={() => setSuccessMessage('')}
          >
            {successMessage}
          </Alert>
        </Zoom>
      )}

      {/* Header */}
      <Box display="flex" alignItems="center" mb={3}>
        <CommentIcon sx={{ mr: 1, color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h5" fontWeight={600}>
          Comments
        </Typography>
        <Chip
          label={comments.length}
          size="small"
          sx={{
            ml: 1.5,
            fontWeight: 600,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
          }}
        />
      </Box>

      {/* Comments List */}
      <Stack spacing={2} mb={3}>
        {comments.length === 0 ? (
          <Paper
            elevation={0}
            sx={{
              p: 4,
              textAlign: 'center',
              bgcolor: 'grey.50',
              border: '2px dashed',
              borderColor: 'grey.300',
              borderRadius: 2,
            }}
          >
            <CommentIcon sx={{ fontSize: 48, color: 'grey.400', mb: 1 }} />
            <Typography variant="body1" color="text.secondary">
              No comments yet. Be the first to comment!
            </Typography>
          </Paper>
        ) : (
          comments.map((comment, index) => (
            <Fade in key={comment.id} timeout={300 + index * 100}>
              <Card
                elevation={0}
                sx={{
                  border: '1px solid',
                  borderColor: 'grey.200',
                  borderRadius: 2,
                  transition: 'all 0.3s ease',
                  '&:hover': {
                    borderColor: comment.comment_type === 'internal' ? 'warning.main' : 'primary.main',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
                    transform: 'translateY(-2px)',
                  },
                }}
              >
                <CardContent sx={{ p: 2.5 }}>
                  {/* Comment Header */}
                  <Box display="flex" alignItems="flex-start" mb={1.5}>
                    <Avatar
                      sx={{
                        width: 40,
                        height: 40,
                        bgcolor: getAvatarColor(comment.author_name),
                        fontWeight: 600,
                        fontSize: 14,
                      }}
                    >
                      {getInitials(comment.author_name)}
                    </Avatar>

                    <Box flex={1} ml={1.5}>
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2" fontWeight={600}>
                          {comment.author_name || 'Unknown User'}
                        </Typography>
                        <Chip
                          icon={comment.comment_type === 'internal' ? <LockIcon /> : <PublicIcon />}
                          label={comment.comment_type === 'internal' ? 'Internal' : 'Public'}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: 11,
                            fontWeight: 600,
                            bgcolor: comment.comment_type === 'internal' ? 'warning.light' : 'success.light',
                            color: comment.comment_type === 'internal' ? 'warning.dark' : 'success.dark',
                            '& .MuiChip-icon': {
                              fontSize: 14,
                            },
                          }}
                        />
                        {comment.edited && (
                          <Typography variant="caption" color="text.secondary" fontStyle="italic">
                            (edited)
                          </Typography>
                        )}
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(comment.created_at)}
                      </Typography>
                    </Box>

                    {/* Action Buttons */}
                    <Stack direction="row" spacing={0.5}>
                      <Tooltip title="Edit comment">
                        <IconButton
                          size="small"
                          onClick={() => handleStartEdit(comment)}
                          sx={{
                            color: 'primary.main',
                            '&:hover': { bgcolor: 'primary.light', transform: 'scale(1.1)' },
                          }}
                        >
                          <EditIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete comment">
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteClick(comment.id)}
                          sx={{
                            color: 'error.main',
                            '&:hover': { bgcolor: 'error.light', transform: 'scale(1.1)' },
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Box>

                  <Divider sx={{ my: 1.5 }} />

                  {/* Comment Content */}
                  {editingComment === comment.id ? (
                    <Box>
                      <TextField
                        fullWidth
                        multiline
                        rows={3}
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        variant="outlined"
                        size="small"
                        sx={{ mb: 1 }}
                      />
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          size="small"
                          onClick={() => setEditingComment(null)}
                          startIcon={<CloseIcon />}
                        >
                          Cancel
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          onClick={handleSaveEdit}
                          startIcon={<CheckCircleIcon />}
                        >
                          Save
                        </Button>
                      </Stack>
                    </Box>
                  ) : (
                    <Typography
                      variant="body2"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        lineHeight: 1.6,
                      }}
                    >
                      {comment.content}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Fade>
          ))
        )}
      </Stack>

      {/* New Comment Form */}
      <Card
        elevation={0}
        sx={{
          border: '2px solid',
          borderColor: 'primary.main',
          borderRadius: 2,
          bgcolor: 'background.paper',
        }}
      >
        <CardContent sx={{ p: 2.5 }}>
          <Typography variant="subtitle2" fontWeight={600} mb={1.5}>
            Add Comment
          </Typography>

          <TextField
            fullWidth
            multiline
            rows={4}
            placeholder="Write your comment here..."
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            variant="outlined"
            sx={{
              mb: 2,
              '& .MuiOutlinedInput-root': {
                fontSize: 14,
              },
            }}
          />

          <Box display="flex" justifyContent="space-between" alignItems="center">
            <ToggleButtonGroup
              value={commentType}
              exclusive
              onChange={(_, value) => value && setCommentType(value)}
              size="small"
            >
              <ToggleButton value={CommentType.PUBLIC}>
                <PublicIcon sx={{ mr: 0.5, fontSize: 18 }} />
                Public
              </ToggleButton>
              <ToggleButton value={CommentType.INTERNAL}>
                <LockIcon sx={{ mr: 0.5, fontSize: 18 }} />
                Internal
              </ToggleButton>
            </ToggleButtonGroup>

            <Button
              variant="contained"
              onClick={handleSubmitComment}
              disabled={!newComment.trim() || submitting}
              startIcon={submitting ? <CircularProgress size={16} /> : <SendIcon />}
              sx={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                px: 3,
                fontWeight: 600,
                '&:hover': {
                  background: 'linear-gradient(135deg, #5568d3 0%, #6a4293 100%)',
                },
              }}
            >
              {submitting ? 'Posting...' : 'Post Comment'}
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography>Are you sure you want to delete this comment? This action cannot be undone.</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleConfirmDelete} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TicketComments;
