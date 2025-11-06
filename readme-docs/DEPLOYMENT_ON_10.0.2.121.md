# Deployment Guide for Server 10.0.2.121

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Server: 10.0.2.121 (This Server)              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  PostgreSQL  │  │    Redis     │  │   Backend    │     │
│  │   :5432      │  │    :6379     │  │   :8000      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                             │                │
│                    ┌──────────────┐         │                │
│                    │   Frontend   │◄────────┘                │
│                    │    :3000     │                          │
│                    └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP Requests
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               LLM Server: 10.0.6.31:8000                    │
│              (qwen2.5-coder-32b via vLLM)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Access URLs

After deployment, the system will be accessible at:

- **Frontend (Admin Portal)**: `http://10.0.2.121:3000`
- **Backend API**: `http://10.0.2.121:8000`
- **API Documentation**: `http://10.0.2.121:8000/api/docs`
- **Health Check**: `http://10.0.2.121:8000/health`

---

## Pre-Deployment Checklist

### 1. Verify LLM Server Connectivity
```bash
# Test connection to LLM server from 10.0.2.121
curl -v http://10.0.6.31:8000/v1/models

# Expected: 200 OK with model list
# If fails, check network connectivity and firewall rules
```

### 2. Update Configuration
```bash
cd /opt/redmine-automation-v2/v3

# Edit .env file
nano .env

# Update these values:
REDMINE_API_KEY=your_actual_api_key_here
GOOGLE_CHAT_WEBHOOK=your_actual_webhook_here
POSTGRES_PASSWORD=your_secure_password_here
```

### 3. Firewall Configuration
```bash
# Allow incoming connections on required ports
sudo firewall-cmd --permanent --add-port=8000/tcp  # Backend API
sudo firewall-cmd --permanent --add-port=3000/tcp  # Frontend
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

---

## Deployment Steps

### Step 1: Prepare Environment
```bash
cd /opt/redmine-automation-v2/v3

# Ensure Docker and Docker Compose are installed
docker --version
docker-compose --version

# Create necessary directories
mkdir -p backend/logs backend/models
chmod 755 backend/logs backend/models
```

### Step 2: Test LLM Connectivity
```bash
# Test from backend container network
docker run --rm curlimages/curl:latest \
  curl -v http://10.0.6.31:8000/v1/models

# Should return 200 OK
```

### Step 3: Build and Start Services
```bash
# Build all containers
docker-compose build

# Start all services
docker-compose up -d

# Watch logs
docker-compose logs -f
```

### Step 4: Verify Services
```bash
# Check container status
docker-compose ps

# All containers should show "Up"
# devops-tickets-db        Up (healthy)
# devops-tickets-redis     Up (healthy)
# devops-tickets-backend   Up (healthy)
# devops-tickets-frontend  Up

# Test health endpoint
curl http://10.0.2.121:8000/health

# Expected response:
{
  "overall_status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### Step 5: Initialize Database
```bash
# Database tables are created automatically on first run
# Check logs to confirm
docker-compose logs backend | grep "Database tables created"
```

### Step 6: Test LLM Integration
```bash
# Test LLM connectivity from backend
docker-compose exec backend python -c "
import requests
response = requests.get('http://10.0.6.31:8000/v1/models', timeout=10)
print('LLM Status:', response.status_code)
print('Models:', response.json())
"

# Should print: LLM Status: 200
```

---

## Access the System

### From Your Local Machine
If you're accessing from another machine, add routes or use SSH tunnel:

**Option A: Direct Access** (if network allows)
```bash
# Just open in browser
http://10.0.2.121:3000  # Frontend
http://10.0.2.121:8000  # API
```

**Option B: SSH Tunnel** (if behind firewall)
```bash
# From your local machine
ssh -L 3000:localhost:3000 -L 8000:localhost:8000 user@10.0.2.121

# Then access via localhost
http://localhost:3000  # Frontend
http://localhost:8000  # API
```

### Test the System
```bash
# 1. Check API is responding
curl http://10.0.2.121:8000/

# 2. Check frontend loads
curl http://10.0.2.121:3000/

# 3. Test ticket processing (manual trigger)
curl -X POST http://10.0.2.121:8000/api/v1/tickets/process

# 4. View API documentation
open http://10.0.2.121:8000/api/docs
```

---

## Network Configuration

### Required Network Access

**From 10.0.2.121 → 10.0.6.31**:
- Port 8000 (HTTP) - LLM API access
- Must be reachable for LLM analysis to work

**From External → 10.0.2.121**:
- Port 3000 (HTTP) - Frontend access
- Port 8000 (HTTP) - API access (optional, can be internal only)

**From 10.0.2.121 → Redmine**:
- Port 443 (HTTPS) - techsupport.6dtech.co.in

### Firewall Rules Summary
```bash
# On 10.0.2.121
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-all
```

---

## Environment-Specific Configuration

### .env File for 10.0.2.121
```env
# Server Configuration
SERVER_IP=10.0.2.121
BACKEND_PORT=8000
FRONTEND_PORT=3000

# LLM Server (External)
LLM_BASE_URL=http://10.0.6.31:8000/v1
LLM_MODEL=qwen2.5-coder-32b
LLM_TIMEOUT=120

# Redmine
REDMINE_BASE_URL=https://techsupport.6dtech.co.in
REDMINE_API_KEY=<YOUR_API_KEY>

# Notifications
GOOGLE_CHAT_WEBHOOK=<YOUR_WEBHOOK>

# Database
POSTGRES_PASSWORD=<SECURE_PASSWORD>
```

### CORS Configuration
The backend is already configured to accept requests from the frontend:
```python
# In main.py - CORS origins
CORS_ORIGINS=http://10.0.2.121:3000,http://localhost:3000
```

---

## Monitoring & Troubleshooting

### Check Service Status
```bash
# All containers
docker-compose ps

# Individual service logs
docker-compose logs backend
docker-compose logs frontend
docker-compose logs postgres
docker-compose logs redis

# Follow logs
docker-compose logs -f backend
```

### Common Issues

#### 1. LLM Connection Timeout
```bash
# Symptom: "LLM call failed: timeout"
# Solution: Verify LLM server is running and accessible

# Test from backend container
docker-compose exec backend curl -v http://10.0.6.31:8000/v1/models

# If fails, check:
# - LLM server is running on 10.0.6.31
# - Port 8000 is open
# - Network route exists
```

#### 2. Cannot Access Frontend
```bash
# Symptom: Cannot load http://10.0.2.121:3000
# Solution: Check frontend container and ports

# Check frontend is running
docker-compose ps frontend

# Check nginx logs
docker-compose logs frontend

# Verify port binding
sudo netstat -tlnp | grep 3000
```

#### 3. Database Connection Error
```bash
# Symptom: "Database unhealthy" in health check
# Solution: Check PostgreSQL container

# Check database logs
docker-compose logs postgres

# Connect to database manually
docker-compose exec postgres psql -U devops_user -d devops_tickets

# If fails, restart database
docker-compose restart postgres
```

#### 4. Redis Connection Issues
```bash
# Check Redis is running
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check Redis logs
docker-compose logs redis

# Clear Redis cache if needed
docker-compose exec redis redis-cli FLUSHALL
```

---

## Performance Monitoring

### Cache Performance
```bash
# Check cache metrics
curl http://10.0.2.121:8000/api/v1/metrics/cache

# Expected output:
{
  "llm_cache": {
    "cache_hits": 145,
    "cache_misses": 55,
    "hit_rate_percent": 72.5
  },
  "redis_memory_mb": 18.5
}
```

### System Health
```bash
# Health check
curl http://10.0.2.121:8000/health

# Scheduler status
docker-compose exec backend python -c "
from app.scheduler.scheduler import get_scheduler_status
print(get_scheduler_status())
"
```

### Resource Usage
```bash
# Container resource usage
docker stats

# Disk usage
docker-compose exec backend df -h

# Database size
docker-compose exec postgres psql -U devops_user -d devops_tickets -c "
SELECT pg_size_pretty(pg_database_size('devops_tickets'));
"
```

---

## Backup & Maintenance

### Database Backup
```bash
# Backup database
docker-compose exec postgres pg_dump -U devops_user devops_tickets > \
  backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
docker-compose exec -T postgres psql -U devops_user devops_tickets < backup.sql
```

### Log Rotation
```bash
# Backend logs are in backend/logs/
# Configure rotation in loguru (already set to 500MB, 10 days retention)

# Manual cleanup if needed
find backend/logs -name "*.log.*" -mtime +30 -delete
```

### Updates
```bash
# Pull latest changes
cd /opt/redmine-automation-v2/v3
git pull  # if using git

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## Production Checklist

Before going live, verify:

- [ ] LLM server (10.0.6.31:8000) is accessible
- [ ] Redmine API key is correct
- [ ] Google Chat webhook is configured
- [ ] Strong PostgreSQL password set
- [ ] Firewall rules are configured
- [ ] All containers show "healthy" status
- [ ] Health endpoint returns "healthy"
- [ ] Can access frontend at http://10.0.2.121:3000
- [ ] Can access API docs at http://10.0.2.121:8000/api/docs
- [ ] Test ticket processing works
- [ ] Cache metrics are being collected
- [ ] Scheduler jobs are running
- [ ] Backups are configured

---

## Support & Troubleshooting

### Quick Tests
```bash
# Test complete system
./test-system.sh  # Creates this script below

# Or manually:
echo "1. Testing Backend..."
curl -f http://10.0.2.121:8000/health || echo "FAILED"

echo "2. Testing Frontend..."
curl -f http://10.0.2.121:3000/ || echo "FAILED"

echo "3. Testing LLM..."
docker-compose exec backend curl -f http://10.0.6.31:8000/v1/models || echo "FAILED"

echo "4. Testing Database..."
docker-compose exec postgres pg_isready || echo "FAILED"

echo "5. Testing Redis..."
docker-compose exec redis redis-cli ping || echo "FAILED"
```

### Get Help
```bash
# View comprehensive logs
docker-compose logs --tail=100

# Check system metrics
curl http://10.0.2.121:8000/api/v1/metrics/cache

# Export logs for debugging
docker-compose logs > system-logs-$(date +%Y%m%d).txt
```

---

## Contact Information

**System**: DevOps Ticket Management v3.0
**Deployment Server**: 10.0.2.121
**LLM Server**: 10.0.6.31
**Frontend**: http://10.0.2.121:3000
**Backend API**: http://10.0.2.121:8000
**Documentation**: http://10.0.2.121:8000/api/docs

---

**Deployment Date**: [To be filled]
**Deployed By**: [To be filled]
**Status**: Production Ready ✅
