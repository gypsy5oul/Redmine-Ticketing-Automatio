# DevOps Ticket Management - Admin Portal

Enterprise-grade React TypeScript admin portal for the DevOps Ticket Management System v3.0.

## Features

### Dashboard
- Real-time metrics and KPIs
- Team workload visualization
- SLA status distribution charts
- At-risk tickets with countdown timers
- Live updates via WebSocket

### Team Management
- CRUD operations for team members
- Skill assignment and management
- Workload configuration
- Performance tracking
- Team level management (L1/L2/L3)

### SLA Configuration
- Edit SLA policies for each priority (P1-P5)
- Configure response, resolution, and escalation times
- Business hours toggle
- Industry standard recommendations

### Ticket Monitoring
- Real-time ticket list with filters
- SLA countdown indicators
- Pause/Resume SLA tracking
- Manual escalation
- Quick access to collaboration workspace

### Analytics
- Ticket volume forecasting (7-day ML prediction)
- Team performance metrics
- Resolution time trends
- SLA compliance tracking
- Date range filtering

### Collaboration Workspace
- Real-time chat via WebSocket
- Multiple collaborators per ticket
- Contribution tracking
- Live presence indicators
- Add/remove collaborators

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Material-UI (MUI)** - Component library
- **Recharts** - Data visualization
- **Socket.IO Client** - WebSocket communication
- **Axios** - HTTP client
- **React Router** - Routing

## Development Setup

### Prerequisites
- Node.js 20+
- npm or yarn

### Installation

```bash
cd /opt/redmine-automation-v2/v3/frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env with your backend URL
nano .env
```

### Environment Variables

```bash
# .env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

### Run Development Server

```bash
npm run dev
```

Open http://localhost:3000

### Build for Production

```bash
npm run build
```

Output will be in `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Docker Deployment

### Build Docker Image

```bash
docker build -t devops-tickets-frontend:v3.0.0 .
```

### Run with Docker

```bash
docker run -p 3000:80 devops-tickets-frontend:v3.0.0
```

### Run with Docker Compose

See main `docker-compose.yml` in the root directory.

```bash
cd /opt/redmine-automation-v2/v3
docker-compose up -d
```

Frontend will be available at http://localhost:3000

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # Reusable components
│   │   └── Layout.tsx   # Main layout with navigation
│   ├── pages/           # Page components
│   │   ├── Dashboard.tsx
│   │   ├── TeamManagement.tsx
│   │   ├── SLAConfiguration.tsx
│   │   ├── TicketMonitoring.tsx
│   │   ├── Analytics.tsx
│   │   └── CollaborationWorkspace.tsx
│   ├── services/        # API and WebSocket clients
│   │   ├── api.ts
│   │   └── websocket.ts
│   ├── types/           # TypeScript type definitions
│   │   └── index.ts
│   ├── App.tsx          # Main app component
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── Dockerfile           # Production Docker image
├── nginx.conf           # Nginx configuration
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
└── vite.config.ts       # Vite config
```

## API Integration

The frontend connects to the backend REST API and WebSocket server.

### REST API
- Base URL: `http://localhost:8000`
- All endpoints are in the `/api/v1/` namespace
- See `src/services/api.ts` for all available endpoints

### WebSocket
- Base URL: `ws://localhost:8000`
- Real-time updates for:
  - SLA status changes
  - Team workload updates
  - Collaboration messages
  - Ticket updates

## Available Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run lint` | Run ESLint |

## Features by Page

### 1. Dashboard (`/dashboard`)
- Total tickets today
- SLA compliance rate
- At-risk tickets count
- Team capacity percentage
- Workload bar chart
- SLA pie chart
- At-risk tickets list with progress bars

### 2. Team Management (`/team`)
- DataGrid with all team members
- Add/Edit/Delete members
- Skill assignment (multi-select)
- Timezone configuration
- Work hours setup
- Performance metrics display

### 3. SLA Configuration (`/sla`)
- Edit SLA policies for P1-P5
- Response time configuration
- Resolution time configuration
- Escalation time configuration
- Business hours toggle
- Recommended times guide

### 4. Ticket Monitoring (`/tickets`)
- Real-time ticket list
- Filters (status, priority, level, SLA)
- SLA countdown with progress bar
- Pause/Resume SLA
- Manual escalation
- Link to Redmine
- Link to collaboration

### 5. Analytics (`/analytics`)
- Ticket volume forecast (7 days)
- Resolution time chart
- SLA compliance chart
- Team performance table
- Date range selection
- Trend indicators

### 6. Collaboration Workspace (`/collaboration/:ticketId`)
- Ticket information header
- Active collaborators list
- Contribution percentages
- Real-time chat
- Add/remove collaborators
- WebSocket status indicator

## Customization

### Theme
Edit `src/main.tsx` to customize MUI theme:

```typescript
const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2', // Change primary color
    },
    // ... other colors
  },
})
```

### Styling
- Global styles: `src/index.css`
- Component styles: Use MUI `sx` prop
- Theme overrides: `src/main.tsx`

## Performance Optimization

- **Code splitting**: Automatic with Vite
- **Lazy loading**: Routes can be lazy-loaded
- **Gzip compression**: Enabled in nginx
- **Asset caching**: Static assets cached for 1 year
- **WebSocket**: Efficient real-time updates

## Security

- **CORS**: Configured in backend
- **XSS Protection**: Security headers in nginx
- **Content Security**: nosniff header
- **Frame protection**: SAMEORIGIN header
- **HTTPS**: Use reverse proxy (nginx/traefik)

## Troubleshooting

### Backend Connection Issues
1. Check `VITE_API_BASE_URL` in `.env`
2. Ensure backend is running on port 8000
3. Check CORS configuration in backend

### WebSocket Not Connecting
1. Check `VITE_WS_BASE_URL` in `.env`
2. Ensure backend WebSocket is enabled
3. Check browser console for errors

### Build Failures
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
npm run build
```

## Browser Support

- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)

## Contributing

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit pull request

## License

Proprietary - Internal Use Only

---

**Version**: 3.0.0
**Last Updated**: 2025-01-27
**Status**: Production Ready
