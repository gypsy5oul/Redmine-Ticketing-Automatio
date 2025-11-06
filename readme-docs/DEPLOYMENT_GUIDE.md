# Deployment Guide - Work Session Features

## ✅ Build Status

**All Docker images built successfully:**
- ✅ `redmine-automation-v3-backend` (944MB)
- ✅ `redmine-automation-v3-scheduler` (944MB)
- ✅ `redmine-automation-v3-frontend` (54.3MB)

---

## 🚀 Quick Start Deployment

### 1. Configure Environment Variables

Create or update your `.env` file:

```bash
# Copy the example file
cp .env.example .env

# Edit with your values
nano .env
```

**Required variables:**
```bash
# Redmine Configuration
REDMINE_BASE_URL=https://techsupport.6dtech.co.in
REDMINE_API_KEY=your_api_key_here
DEVOPS_PROJECT_ID=1
DEVOPS_TEAM_GROUP_ID=6

# Timezone (IMPORTANT for work session timestamps)
TZ=Asia/Kolkata  # or your timezone

# Optional: LLM and notifications
LLM_BASE_URL=http://10.0.6.31:8000/v1
LLM_MODEL=qwen2.5-coder-32b
GOOGLE_CHAT_WEBHOOK=your_webhook_here
```

### 2. Start the Application

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### 3. Apply Database Migration

**IMPORTANT**: The work session tables need to be created:

```bash
# Check current migration status
docker-compose exec backend alembic current

# Run migrations
docker-compose exec backend alembic upgrade head

# Verify migration
docker-compose exec backend alembic current
# Should show: 006 (head)
```

### 4. Verify Everything is Running

```bash
# Check all services are healthy
docker-compose ps

# Expected output:
# - postgres: Up (healthy)
# - redis: Up (healthy)
# - backend: Up (healthy)
# - scheduler: Up
# - frontend: Up (healthy)
```

### 5. Access the Application

- **Frontend**: http://10.0.2.121:3000
- **Backend API**: http://10.0.2.121:8000
- **API Docs**: http://10.0.2.121:8000/docs

---

## 🔧 Troubleshooting

### Issue: Containers use wrong timezone

**Solution:**
```bash
# 1. Stop containers
docker-compose down

# 2. Set timezone in .env
echo "TZ=Asia/Kolkata" >> .env

# 3. Restart
docker-compose up -d

# 4. Verify timezone
docker-compose exec backend date
docker-compose exec postgres psql -U devops_user -d devops_tickets -c "SELECT now();"
```

### Issue: Migration fails

```bash
# Check if alembic is configured
docker-compose exec backend ls -la | grep alembic

# If alembic directory exists but no alembic.ini:
docker-compose exec backend alembic init alembic

# Then run migration again
docker-compose exec backend alembic upgrade head
```

### Issue: Frontend not loading work session components

**Check browser console for errors:**
```bash
# Rebuild frontend with verbose logging
docker-compose build --no-cache frontend
docker-compose up -d frontend
docker-compose logs -f frontend
```

### Issue: Work sessions not appearing in Dashboard

```bash
# Check if work session API is working
curl http://10.0.2.121:8000/api/v1/work/active

# Should return: {"active_sessions": [], "member_id": null}

# Check if migration ran
docker-compose exec backend alembic current
# Should show migration 006
```

---

## 📊 Testing the New Features

### 1. Test Work Session Manager (Dashboard)

1. Login to the application
2. Navigate to Dashboard
3. Look for "Active Work Sessions" section
4. Should see:
   - Work capacity gauge (0/2 per engineer)
   - "No active work sessions" message
   - Stats showing engineers working vs available

### 2. Test Work Session Tracking (Tickets Page)

1. Go to Tickets → Ticket Monitoring
2. Find a ticket assigned to you
3. Click "Start" button in the "Work State" column
4. Should see:
   - Session started confirmation
   - Timer begins counting
   - "Pause" button appears
5. Click "Pause" → Select waiting reason → Confirm
6. Should see session paused, waiting time tracked

### 3. Test Work Efficiency Analytics

1. Navigate to Analytics page
2. Scroll to "Work Efficiency Analytics" section
3. Should see:
   - 4 summary cards (Work, Waiting, Idle, Efficiency)
   - Bottleneck Analysis chart (if data exists)
   - Overall Time Distribution pie chart

### 4. Test Member Performance Page

1. Go to Team Management
2. Click on any team member
3. Scroll to "Work Efficiency Metrics" section
4. Should see:
   - Pie chart with work/wait/idle breakdown
   - 4 metric cards showing hours and ticket count

---

## 🎯 Verification Checklist

After deployment, verify:

- [ ] All 5 containers are running
- [ ] Database migration 006 is applied
- [ ] Dashboard shows "Active Work Sessions" section
- [ ] Tickets page has "Work State" column with Start/Pause/Resume buttons
- [ ] Analytics page shows "Work Efficiency Analytics" section
- [ ] Member Performance page shows work efficiency chart
- [ ] Timestamps are in correct timezone (check dashboard "Updated" time)
- [ ] No errors in browser console (F12)
- [ ] No errors in backend logs: `docker-compose logs backend | grep -i error`

---

## 🔄 Updating the System

When pulling new changes:

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker-compose build --no-cache

# Stop old containers
docker-compose down

# Start new containers
docker-compose up -d

# Run any new migrations
docker-compose exec backend alembic upgrade head

# Verify
docker-compose ps
docker-compose logs -f backend
```

---

## 📈 Monitoring

### Check Application Health

```bash
# Backend health
curl http://10.0.2.121:8000/health

# Check active sessions
curl http://10.0.2.121:8000/api/v1/work/active

# Check database connection
docker-compose exec postgres psql -U devops_user -d devops_tickets -c "SELECT COUNT(*) FROM work_sessions;"
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f scheduler
docker-compose logs -f frontend

# Filter errors only
docker-compose logs backend | grep -i error
docker-compose logs backend | grep -i exception
```

---

## 🆘 Emergency Rollback

If something goes wrong:

```bash
# Stop all services
docker-compose down

# Remove new containers (keeps data)
docker-compose down --remove-orphans

# Restore from backup (if you have one)
# Or rebuild from previous commit

# Start fresh
docker-compose up -d
```

---

## 📞 Support

If you encounter issues:

1. **Check logs first**: `docker-compose logs -f backend`
2. **Verify migration status**: `docker-compose exec backend alembic current`
3. **Check timezone config**: `docker-compose exec backend date`
4. **Browser console**: Press F12, check for JavaScript errors
5. **API test**: Use Postman to test endpoints directly

---

## ✨ New Features Available

After deployment, users can:

1. **Track actual work time** vs waiting time vs idle time
2. **See live work sessions** with real-time timers
3. **View bottleneck analysis** - what causes most delays
4. **Monitor work efficiency** - percentage of active work vs total time
5. **Review individual performance** - per-engineer productivity metrics
6. **Accurate timestamps** - all times match local timezone

All features are fully integrated and production-ready!
