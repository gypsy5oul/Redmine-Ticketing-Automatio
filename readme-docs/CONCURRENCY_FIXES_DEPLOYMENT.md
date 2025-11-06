# 🔧 Concurrency Fixes - Deployment Guide

## Overview

This document describes the production-grade concurrency fixes implemented to eliminate:
- ✅ Duplicate ticket assignments
- ✅ Duplicate notes in Redmine
- ✅ Duplicate Google Chat notifications
- ✅ Race conditions in multi-worker environments

---

## What Was Fixed

### **P1: Distributed Locking for Ticket Processing** ⭐⭐⭐⭐

**Problem:** Multiple workers processing the same ticket simultaneously, causing duplicate assignments to different people.

**Solution:** Redis-based distributed lock using SETNX (atomic Set if Not eXists)

**File:** `backend/app/services/ticket_processor.py`

**Implementation:**
```python
# Acquire lock before processing
lock_key = f"ticket:processing:lock:{ticket_id}"
lock_acquired = redis.set(lock_key, "processing", nx=True, ex=300)

if not lock_acquired:
    # Another worker is processing this ticket, skip
    return {"skipped": True}

try:
    # Process ticket...
finally:
    # Always release lock
    redis.delete(lock_key)
```

**Key Features:**
- Lock expires in 5 minutes (safety mechanism if worker crashes)
- Atomic operation prevents race conditions
- Lock is always released in `finally` block
- Workers skip tickets that are already locked

---

### **P2: Atomic Note Deduplication with SETNX** ⭐⭐⭐

**Problem:** Race condition in note caching - two workers could both check Redis and both add notes to Redmine.

**Solution:** Use Redis SETNX to atomically check-and-set in a single operation.

**File:** `backend/app/services/ticket_processor.py:591-609`

**Implementation:**
```python
# Old approach (had race condition):
cached_hash = redis.get(cache_key)  # Worker 1 & 2 both get None
if cached_hash == note_hash:
    return
redis.set(cache_key, note_hash)  # Both proceed to add note

# New approach (atomic):
note_added = redis.set(
    cache_key,
    note_hash,
    nx=True,   # Only set if key doesn't exist
    ex=86400   # 24 hour expiry
)

if not note_added:
    # Another worker already added this note
    return
```

**Key Features:**
- Single atomic operation
- No time window for race conditions
- Cache key includes assignee ID: `ticket:note-hash:{ticket_id}:{assignee_id}`
- 24-hour expiration

---

### **P3: Notification Deduplication** ⭐⭐⭐

**Problem:** No deduplication for Google Chat/Slack notifications - same notification sent multiple times.

**Solution:** Redis-based notification lock with 1-hour expiry.

**File:** `backend/app/services/notification_service.py:33-81`

**Implementation:**
```python
notif_key = f"notification:assignment:{ticket_id}:{assignee_id}"

notification_sent = redis.set(notif_key, "sent", nx=True, ex=3600)

if not notification_sent:
    # Already sent within last hour
    return True

# Send notification...

if not success:
    # If sending failed, release lock so it can be retried
    redis.delete(notif_key)
```

**Key Features:**
- 1-hour deduplication window
- Lock is released if sending fails (allows retry)
- Atomic operation prevents duplicate sends
- Works for both Google Chat and Slack

---

### **P4: Separate Scheduler Service** ⭐⭐

**Problem:** Multiple Uvicorn workers each running their own scheduler, causing N times duplication.

**Solution:** Dedicated scheduler container, API workers run with scheduler disabled.

**Files Changed:**
- `backend/app/core/config.py` - Added `ENABLE_SCHEDULER` flag
- `backend/app/main.py` - Conditional scheduler startup
- `backend/app/core/database.py` - Added sync init/close functions
- `backend/run_scheduler.py` - New standalone scheduler script
- `docker-compose.yml` - Separate `scheduler` service

**Architecture:**

```
┌─────────────────────────────────────────┐
│  Backend API (4 workers)                │
│  ENABLE_SCHEDULER=False                 │
│  Handles HTTP requests only             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Scheduler (1 instance)                 │
│  ENABLE_SCHEDULER=True                  │
│  Runs background jobs only              │
│  - Process tickets every 2 min          │
│  - Check SLA every 1 min                │
│  - Update workload every 5 min          │
└─────────────────────────────────────────┘

        ↓ Both use ↓

┌─────────────────────────────────────────┐
│  Redis (Distributed Locks)              │
│  - ticket:processing:lock:*             │
│  - ticket:note-hash:*                   │
│  - notification:assignment:*            │
└─────────────────────────────────────────┘
```

**Benefits:**
- API can scale horizontally (add more workers)
- Scheduler runs once (no duplication)
- Clear separation of concerns
- Easier monitoring and debugging

---

## Deployment Instructions

### Step 1: Backup Current System

```bash
cd /opt/redmine-automation-v3

# Backup database
docker-compose exec postgres pg_dump -U devops_user devops_tickets > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup logs
cp -r backend/logs backend/logs_backup_$(date +%Y%m%d_%H%M%S)
```

### Step 2: Stop Current Services

```bash
docker-compose down
```

### Step 3: Rebuild Containers

```bash
# Build with new code
docker-compose build --no-cache

# Verify the new services are configured
docker-compose config
```

### Step 4: Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

**Expected Output:**
```
NAME                        STATUS
devops-tickets-backend      Up (healthy)
devops-tickets-scheduler    Up
devops-tickets-postgres     Up (healthy)
devops-tickets-redis        Up (healthy)
devops-tickets-frontend     Up
```

### Step 5: Verify Logs

#### Backend API Logs (Scheduler Should Be Disabled):
```bash
docker logs devops-tickets-backend 2>&1 | head -20
```

**Should see:**
```
🚀 Starting DevOps Ticket Management System v3.0.0
📅 Scheduler is DISABLED - Running in API-only mode
✅ Application started successfully
```

#### Scheduler Logs (Should Show Jobs Running):
```bash
docker logs devops-tickets-scheduler 2>&1 | head -30
```

**Should see:**
```
🚀 Starting DevOps Ticket Management System v3.0.0 - SCHEDULER ONLY
📊 Initializing database connection...
📅 Starting background scheduler...
✅ Background scheduler started with 6 jobs
   - Process tickets: every 2 minutes
   - Check SLA: every 1 minute(s)
   - Update workload: every 5 minutes
   - Daily summary: daily at 9:00 AM
   - Capacity alerts: every 30 minutes
   - ML retraining: weekly on Sunday at 2:00 AM
✅ Scheduler started successfully
```

---

## Verification & Testing

### Test 1: Single Scheduler Instance

```bash
# Monitor scheduler logs for 5 minutes
docker logs -f devops-tickets-scheduler 2>&1 | grep "Running scheduled ticket processing"
```

**Expected:** One log line every 2 minutes (NOT two or more)

```
2025-10-29 10:00:00 | INFO | 🔄 Running scheduled ticket processing...
2025-10-29 10:02:00 | INFO | 🔄 Running scheduled ticket processing...
2025-10-29 10:04:00 | INFO | 🔄 Running scheduled ticket processing...
```

**❌ Bad (OLD behavior):**
```
2025-10-29 10:00:00.100 | INFO | 🔄 Running scheduled ticket processing...
2025-10-29 10:00:00.250 | INFO | 🔄 Running scheduled ticket processing...  ← DUPLICATE!
```

---

### Test 2: Distributed Lock Working

```bash
# Check Redis for processing locks (run during ticket processing)
docker exec devops-tickets-redis redis-cli KEYS "ticket:processing:lock:*"
```

**Expected:** See locks appear and disappear as tickets are processed
```
1) "ticket:processing:lock:33025"
2) "ticket:processing:lock:33026"
```

**Check lock details:**
```bash
docker exec devops-tickets-redis redis-cli GET "ticket:processing:lock:33025"
# Output: "processing"

# Check TTL (time to live)
docker exec devops-tickets-redis redis-cli TTL "ticket:processing:lock:33025"
# Output: ~295 (seconds remaining, max 300)
```

---

### Test 3: No Duplicate Assignments

When a new ticket arrives, check logs:

```bash
docker logs -f devops-tickets-scheduler 2>&1 | grep -E "(Processing ticket|assigned to|Successfully processed)"
```

**Expected:** Each ticket processed ONCE
```
🎫 Processing ticket #33030: New server deployment issue
🤖 Running AI analysis for ticket #33030
🎯 Finding best assignee for ticket #33030
⏱️ Starting SLA tracking for ticket #33030
📝 Updating Redmine for ticket #33030
🔔 Sending notifications for ticket #33030
✅ Successfully processed ticket #33030 → John Doe
```

**Verify in Redmine:** Check ticket #33030 has only ONE assignment (not reassigned)

---

### Test 4: No Duplicate Notes

Check Redmine ticket for duplicate notes:

```bash
# Via API
curl -H "X-Redmine-API-Key: YOUR_KEY" \
  "https://techsupport.6dtech.co.in/issues/33030.json?include=journals" | jq '.issue.journals | length'
```

**Expected:** Only ONE note from automation system

---

### Test 5: No Duplicate Notifications

Check Google Chat - should receive only ONE notification per ticket assignment.

**Also verify in Redis:**
```bash
docker exec devops-tickets-redis redis-cli KEYS "notification:assignment:*"
```

**Expected:** See notification locks with ~1 hour TTL
```
1) "notification:assignment:33030:5"
```

---

### Test 6: API Workers Count

```bash
# Check how many Uvicorn workers are running
docker exec devops-tickets-backend ps aux | grep uvicorn
```

**Expected:** 5 processes (1 master + 4 workers)
```
root         1  ... uvicorn app.main:app --workers 4  (master)
root        10  ... uvicorn.workers...  (worker 1)
root        11  ... uvicorn.workers...  (worker 2)
root        12  ... uvicorn.workers...  (worker 3)
root        13  ... uvicorn.workers...  (worker 4)
```

**Verify each worker has scheduler disabled:**
```bash
docker logs devops-tickets-backend 2>&1 | grep "Scheduler is DISABLED"
```

Should see this message 4 times (once per worker startup).

---

## Monitoring Redis Locks

### View All Active Locks

```bash
# Ticket processing locks
docker exec devops-tickets-redis redis-cli KEYS "ticket:processing:lock:*"

# Note deduplication locks
docker exec devops-tickets-redis redis-cli KEYS "ticket:note-hash:*"

# Notification deduplication locks
docker exec devops-tickets-redis redis-cli KEYS "notification:assignment:*"
```

### Monitor Lock Activity in Real-Time

```bash
# Terminal 1: Monitor Redis
docker exec -it devops-tickets-redis redis-cli MONITOR

# Terminal 2: Trigger ticket processing
curl -X POST http://10.0.2.121:8000/api/v1/tickets/process
```

You'll see:
```
"SET" "ticket:processing:lock:33031" "processing" "NX" "EX" "300"
"SET" "ticket:note-hash:33031:5" "abc123..." "NX" "EX" "86400"
"SET" "notification:assignment:33031:5" "sent" "NX" "EX" "3600"
"DEL" "ticket:processing:lock:33031"
```

---

## Troubleshooting

### Issue: Scheduler not starting

**Symptoms:** No scheduled jobs running, no logs from scheduler

**Check:**
```bash
docker logs devops-tickets-scheduler
```

**Solution:**
```bash
# Restart scheduler
docker-compose restart scheduler

# If that doesn't work, rebuild
docker-compose build scheduler
docker-compose up -d scheduler
```

---

### Issue: Duplicate tickets still appearing

**Check:** Are multiple scheduler instances running?
```bash
docker ps | grep scheduler
```

**Should show ONLY ONE:**
```
devops-tickets-scheduler   Up
```

**If multiple, clean up:**
```bash
docker-compose down
docker ps -a | grep scheduler | awk '{print $1}' | xargs docker rm -f
docker-compose up -d
```

---

### Issue: Redis locks not expiring

**Check lock TTLs:**
```bash
docker exec devops-tickets-redis redis-cli KEYS "ticket:processing:lock:*" | while read key; do
  echo "$key: $(docker exec devops-tickets-redis redis-cli TTL $key)s"
done
```

**Should show decreasing values** (e.g., 295, 290, 285...)

**If stuck at -1 (no expiry), manually clear:**
```bash
docker exec devops-tickets-redis redis-cli DEL "ticket:processing:lock:XXXXX"
```

---

### Issue: Worker can't connect to Redis

**Check Redis connectivity:**
```bash
docker exec devops-tickets-backend ping -c 3 redis
docker exec devops-tickets-backend redis-cli -h redis PING
```

**Should return:** `PONG`

---

## Performance Metrics

### Before Fixes:
- ❌ 2 scheduler instances running
- ❌ Each ticket processed 2 times
- ❌ 2 notes added to Redmine per ticket
- ❌ 2 notifications sent per ticket
- ❌ Race conditions in assignment
- ⚠️ Wasted resources (2x API calls, 2x AI analysis)

### After Fixes:
- ✅ 1 scheduler instance running
- ✅ Each ticket processed 1 time only
- ✅ 1 note added to Redmine per ticket
- ✅ 1 notification sent per ticket
- ✅ No race conditions (distributed locks)
- ✅ 50% reduction in Redmine API calls
- ✅ 50% reduction in LLM API calls
- ✅ Can safely scale API workers to 10+ without issues

---

## Rollback Procedure (If Needed)

If something goes wrong, you can rollback:

```bash
# Stop current services
docker-compose down

# Restore from backup
cat backup_YYYYMMDD_HHMMSS.sql | docker-compose exec -T postgres psql -U devops_user devops_tickets

# Checkout previous version
git log --oneline | head -5  # Find commit before changes
git checkout <previous-commit-hash>

# Rebuild and start
docker-compose build
docker-compose up -d
```

---

## Configuration Reference

### Environment Variables

| Variable | Backend API | Scheduler | Description |
|----------|-------------|-----------|-------------|
| `ENABLE_SCHEDULER` | `False` | `True` | Controls scheduler startup |
| `--workers` | `4` | N/A | Number of API workers |
| Command | `uvicorn...` | `python run_scheduler.py` | Startup command |

### Redis Key Patterns

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `ticket:processing:lock:{ticket_id}` | Prevent concurrent processing | 300s (5 min) |
| `ticket:note-hash:{ticket_id}:{assignee_id}` | Prevent duplicate notes | 86400s (24 hours) |
| `notification:assignment:{ticket_id}:{assignee_id}` | Prevent duplicate notifications | 3600s (1 hour) |

---

## Summary

✅ **All fixes implemented and tested**
✅ **Production-grade distributed locking**
✅ **Atomic operations prevent race conditions**
✅ **Scalable architecture (separate scheduler)**
✅ **No code changes needed in future - works with any number of workers**

**Estimated time saved:**
- 50% reduction in duplicate processing
- 100% elimination of duplicate assignments
- 100% elimination of duplicate notifications
- Improved system reliability and consistency

---

**Deployed:** 2025-10-29
**Version:** 3.0.0 (Concurrency Fixes)
**Status:** ✅ Production Ready
