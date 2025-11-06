import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import apiClient from '@/services/api'
import ChangePasswordDialog from '@/components/ChangePasswordDialog'

interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  role: string
  active: boolean
  force_password_change?: boolean
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isAdmin: boolean
  isManager: boolean
  isSuperAdmin: boolean
  requiresPasswordChange: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [showPasswordDialog, setShowPasswordDialog] = useState(false)

  // Load user from localStorage and verify token on mount
  useEffect(() => {
    const loadUser = async () => {
      const token = localStorage.getItem('access_token')
      const storedUser = localStorage.getItem('user')

      if (token && storedUser) {
        try {
          // Verify token by fetching current user
          const response = await apiClient.client.get('/api/v1/auth/me')
          setUser(response.data)
        } catch (error) {
          console.error('Token verification failed:', error)
          // Token invalid, clear storage
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user')
          setUser(null)
        }
      }
      setIsLoading(false)
    }

    loadUser()
  }, [])

  const login = async (username: string, password: string) => {
    const response = await apiClient.client.post('/api/v1/auth/login', {
      username,
      password,
    })

    const { access_token, refresh_token, user: userData } = response.data

    // Store tokens and user info
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user', JSON.stringify(userData))

    setUser(userData)

    // Check if password change is required
    if (userData.force_password_change) {
      setShowPasswordDialog(true)
    }
  }

  const logout = () => {
    // Clear storage
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')

    setUser(null)

    // Optional: Call backend logout endpoint
    apiClient.client.post('/api/v1/auth/logout').catch(() => {
      // Ignore errors on logout
    })
  }

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const isManager = user?.role === 'manager' || isAdmin
  const isSuperAdmin = user?.role === 'super_admin'
  const requiresPasswordChange = !!user?.force_password_change

  const handlePasswordChangeSuccess = () => {
    // Update user object to clear force_password_change flag
    if (user) {
      const updatedUser = { ...user, force_password_change: false }
      setUser(updatedUser)
      localStorage.setItem('user', JSON.stringify(updatedUser))
    }
    setShowPasswordDialog(false)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        isAdmin,
        isManager,
        isSuperAdmin,
        requiresPasswordChange,
      }}
    >
      {children}
      <ChangePasswordDialog
        open={showPasswordDialog}
        onClose={() => setShowPasswordDialog(false)}
        onSuccess={handlePasswordChangeSuccess}
        required={requiresPasswordChange}
      />
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
