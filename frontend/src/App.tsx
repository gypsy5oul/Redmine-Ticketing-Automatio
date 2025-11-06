import { useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Box, CircularProgress } from '@mui/material'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { queryClient } from './lib/queryClient'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import TeamManagement from './pages/TeamManagement'
import MemberPerformance from './pages/MemberPerformance'
import SLAConfiguration from './pages/SLAConfiguration'
import TicketMonitoring from './pages/TicketMonitoring'
import Analytics from './pages/Analytics'
import CollaborationWorkspace from './pages/CollaborationWorkspace'
import Scheduling from './pages/Scheduling'
import Projects from './pages/Projects'
import ProjectDetailPage from './pages/ProjectDetail'
import wsService from './services/websocket'

// Protected Route Component
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

// App Content (needs to be inside AuthProvider)
function AppContent() {
  const { isAuthenticated } = useAuth()

  useEffect(() => {
    if (isAuthenticated) {
      // Initialize WebSocket connection only if authenticated
      wsService.connect()
      return () => {
        wsService.disconnect()
      }
    }
  }, [isAuthenticated])

  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<Login />} />

      {/* Protected Routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Navigate to="/dashboard" replace />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/team"
        element={
          <ProtectedRoute>
            <Layout>
              <TeamManagement />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/team/performance/:memberId"
        element={
          <ProtectedRoute>
            <Layout>
              <MemberPerformance />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/sla"
        element={
          <ProtectedRoute>
            <Layout>
              <SLAConfiguration />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/tickets"
        element={
          <ProtectedRoute>
            <Layout>
              <TicketMonitoring />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <Layout>
              <Projects />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:projectId"
        element={
          <ProtectedRoute>
            <Layout>
              <ProjectDetailPage />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/analytics"
        element={
          <ProtectedRoute>
            <Layout>
              <Analytics />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/collaboration/:ticketId"
        element={
          <ProtectedRoute>
            <Layout>
              <CollaborationWorkspace />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/scheduling"
        element={
          <ProtectedRoute>
            <Layout>
              <Scheduling />
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

// Main App Component with QueryClient and AuthProvider
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
      {/* React Query Devtools - only visible in development */}
      <ReactQueryDevtools initialIsOpen={false} position="bottom" />
    </QueryClientProvider>
  )
}

export default App
