import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Badge,
  Menu,
  MenuItem,
  Avatar,
  Chip,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import DashboardIcon from '@mui/icons-material/Dashboard'
import PeopleIcon from '@mui/icons-material/People'
import TimerIcon from '@mui/icons-material/Timer'
import ConfirmationNumberIcon from '@mui/icons-material/ConfirmationNumber'
import AnalyticsIcon from '@mui/icons-material/Analytics'
import GroupWorkIcon from '@mui/icons-material/GroupWork'
import NotificationsIcon from '@mui/icons-material/Notifications'
import LogoutIcon from '@mui/icons-material/Logout'
import FolderIcon from '@mui/icons-material/Folder'
import { useAuth } from '../contexts/AuthContext'

const drawerWidth = 260

interface LayoutProps {
  children: React.ReactNode
}

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard', roles: ['VIEWER', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'] },
  { text: 'Team Management', icon: <PeopleIcon />, path: '/team', roles: ['ADMIN', 'SUPER_ADMIN'] },
  { text: 'SLA Configuration', icon: <TimerIcon />, path: '/sla', roles: ['ADMIN', 'SUPER_ADMIN'] },
  { text: 'Ticket Monitoring', icon: <ConfirmationNumberIcon />, path: '/tickets', roles: ['VIEWER', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'] },
  { text: 'Projects', icon: <FolderIcon />, path: '/projects', roles: ['VIEWER', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'] },
  { text: 'Scheduling', icon: <GroupWorkIcon />, path: '/scheduling', roles: ['VIEWER', 'MANAGER', 'ADMIN', 'SUPER_ADMIN'] },
  { text: 'Analytics', icon: <AnalyticsIcon />, path: '/analytics', roles: ['MANAGER', 'ADMIN', 'SUPER_ADMIN'] },
]

export default function Layout({ children }: LayoutProps) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen)
  }

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget)
  }

  const handleUserMenuClose = () => {
    setAnchorEl(null)
  }

  const handleLogout = () => {
    handleUserMenuClose()
    logout()
    navigate('/login')
  }

  // Filter menu items based on user role
  const userRole = user?.role?.toUpperCase() || 'VIEWER'
  const filteredMenuItems = menuItems.filter((item) =>
    item.roles.includes(userRole)
  )

  const drawer = (
    <div>
      <Toolbar>
        <Typography variant="h6" noWrap component="div">
          DevOps Tickets
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        {filteredMenuItems.map((item) => (
          <ListItem key={item.text} disablePadding>
            <ListItemButton
              selected={location.pathname === item.path}
              onClick={() => {
                navigate(item.path)
                setMobileOpen(false)
              }}
            >
              <ListItemIcon>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </div>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <AppBar
        position="fixed"
        sx={{
          width: '100%',
          ml: 0,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="open drawer"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            {filteredMenuItems.find((item) => item.path === location.pathname)?.text || 'DevOps Ticket Management'}
          </Typography>
          <IconButton color="inherit">
            <Badge badgeContent={0} color="error">
              <NotificationsIcon />
            </Badge>
          </IconButton>
          <IconButton
            color="inherit"
            onClick={handleUserMenuOpen}
            sx={{ ml: 1 }}
          >
            <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.dark' }}>
              {user?.username?.charAt(0).toUpperCase()}
            </Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleUserMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <Box sx={{ px: 2, py: 1 }}>
              <Typography variant="subtitle1" fontWeight="bold">
                {user?.full_name || user?.username}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {user?.email}
              </Typography>
              <Chip
                label={user?.role?.replace('_', ' ')}
                size="small"
                color="primary"
                sx={{ mt: 1 }}
              />
            </Box>
            <Divider />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText>Logout</ListItemText>
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      <Box
        component="nav"
        sx={{ flexShrink: 0 }}
      >
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{
            keepMounted: true,
          }}
          sx={{
            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: drawerWidth },
          }}
        >
          {drawer}
        </Drawer>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: 8,
          backgroundColor: '#f5f5f5',
          width: '100%',
        }}
      >
        {children}
      </Box>
    </Box>
  )
}
