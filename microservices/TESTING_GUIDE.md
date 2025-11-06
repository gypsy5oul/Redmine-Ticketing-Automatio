# Complete Testing and Validation Guide

**Purpose**: Step-by-step guide to build, test, and validate all 11 microservices
**Status**: All scripts created and ready to use

---

## Quick Start (One Command)

```bash
cd /opt/redmine-automation-microservice/microservices
./build-and-test.sh
```

This single command will:
1. ✅ Check prerequisites (Docker, Docker Compose)
2. ✅ Stop existing containers
3. ✅ Build all 11 services (~15-20 minutes)
4. ✅ Start all services
5. ✅ Check container status
6. ✅ Analyze logs for errors
7. ✅ Test all health endpoints
8. ✅ Generate comprehensive report

---

## Testing Scripts Available

### 1. **build-and-test.sh** (Complete Build & Test)

**Purpose**: Full automated build, start, and validation

**Usage**:
```bash
./build-and-test.sh
```

**What it does**:
- Validates prerequisites
- Builds all services from scratch
- Starts all containers
- Checks container health
- Analyzes logs for errors
- Tests all health endpoints
- Generates pass/fail report

**Output**: Comprehensive test results with pass/fail status

**Time**: ~20-30 minutes (first time)

---

### 2. **check-status.sh** (Quick Status Check)

**Purpose**: Fast status check of running services

**Usage**:
```bash
./check-status.sh
```

**What it does**:
- Shows container status (running/stopped)
- Tests infrastructure (PostgreSQL, Redis, Kong, RabbitMQ)
- Tests all 11 microservice health endpoints
- Provides quick overview

**Output**: Color-coded status summary

**Time**: ~10 seconds

---

### 3. **analyze-logs.sh** (Log Analysis)

**Purpose**: Analyze logs from all services for errors

**Usage**:
```bash
./analyze-logs.sh
```

**What it does**:
- Checks all service logs
- Identifies critical errors (ModuleNotFoundError, ImportError, etc.)
- Shows database connection issues
- Reports warnings
- Analyzes infrastructure logs

**Output**: Detailed error report with log excerpts

**Time**: ~30 seconds

---

### 4. **validate-dependencies.sh** (Dependency Check)

**Purpose**: Verify all required dependencies are in requirements.txt

**Usage**:
```bash
./validate-dependencies.sh
```

**What it does**:
- Analyzes imports in each service's main.py
- Checks if imports are in requirements.txt
- Identifies missing dependencies
- Validates critical packages (jose, passlib, requests, etc.)

**Output**: List of missing dependencies (if any)

**Time**: ~5 seconds

---

### 5. **setup-kong-routes.sh** (Kong Configuration)

**Purpose**: Configure Kong API Gateway routes

**Usage**:
```bash
./setup-kong-routes.sh
```

**What it does**:
- Waits for Kong to be ready
- Creates service entries in Kong
- Creates routes for all 11 microservices
- Adds ML and work session endpoints

**Output**: Confirmation of route creation

**Time**: ~30 seconds

**When to run**: After services are running

---

### 6. **setup-kong-cors.sh** (CORS Configuration)

**Purpose**: Enable CORS for frontend access

**Usage**:
```bash
./setup-kong-cors.sh
```

**What it does**:
- Configures CORS plugin in Kong
- Allows frontend origins (localhost, dev server, production)
- Sets allowed methods and headers

**Output**: CORS configuration confirmation

**Time**: ~10 seconds

**When to run**: After Kong routes are configured

---

## Complete Testing Workflow

### Step 1: Validate Dependencies
```bash
./validate-dependencies.sh
```

**Expected**: ✅ All dependencies validated

If you see missing dependencies, they've already been fixed. Just pull latest code.

---

### Step 2: Build and Test Everything
```bash
./build-and-test.sh
```

**Expected Output**:
```
==========================================
BUILD & TEST SUMMARY
==========================================

Total Checks: 45
Passed: 45
Failed: 0
Warnings: 0

✓ ALL TESTS PASSED!
```

**First Build**: ~15-20 minutes
**Subsequent Builds**: ~3-5 minutes (with cache)

---

### Step 3: Configure Kong Routes
```bash
./setup-kong-routes.sh
```

**Expected Output**:
```
Creating auth-service... ✓
Creating ticket-service... ✓
...
✅ All Kong routes configured!
```

---

### Step 4: Configure CORS
```bash
./setup-kong-cors.sh
```

**Expected Output**:
```
✓ CORS plugin configured successfully!
```

---

### Step 5: Verify Everything
```bash
./check-status.sh
```

**Expected**: All services showing ✓ Ready

---

## Troubleshooting

### Build Fails

**Check build logs**:
```bash
cat build.log | tail -50
```

**Common issues**:
- Missing dependencies → Check DEPENDENCY_FIXES.md
- Docker out of space → `docker system prune -a`
- Network issues → Check internet connection

---

### Service Won't Start

**Check specific service logs**:
```bash
docker logs <service-name>
```

**Example**:
```bash
docker logs sla-service
```

**Common issues**:
- ModuleNotFoundError → Missing dependency in requirements.txt
- Connection refused → Database not ready yet (wait 30s)
- Port already in use → Stop conflicting service

---

### Health Endpoint Fails

**Test directly**:
```bash
curl http://localhost:8001/health  # auth-service
curl http://localhost:8002/health  # ticket-service
# etc.
```

**Common issues**:
- Connection refused → Service not started
- 404 Not Found → Service doesn't have /health endpoint
- Timeout → Service crashed (check logs)

---

### Container Keeps Restarting

**Check restart count**:
```bash
docker ps -a | grep <service-name>
```

**View full logs**:
```bash
docker logs <service-name> 2>&1 | less
```

**Common issues**:
- Crash on startup → Code error in main.py
- Database connection failed → Check .env DATABASE_URL
- Missing environment variable → Check .env file

---

## Manual Testing Commands

### Check All Containers
```bash
docker ps

# Expected: 16 containers running
# - 1 PostgreSQL (app data)
# - 1 PostgreSQL (Kong data)
# - 1 Redis
# - 1 Kong Gateway
# - 1 RabbitMQ
# - 11 Microservices
```

### Check Database
```bash
docker exec devops-tickets-postgres psql -U devops_user -d devops_tickets -c "\dt"

# Should show tables: users, tickets, team_members, etc.
```

### Check Redis
```bash
docker exec devops-tickets-redis redis-cli ping

# Should return: PONG
```

### Check Kong
```bash
curl http://localhost:8444/services

# Should return JSON list of services
```

### Check RabbitMQ
```bash
# Open browser
http://localhost:15672

# Login: devops_user / devops_password_change_this
```

### Test Microservices Through Kong
```bash
# Auth service
curl http://localhost:8000/api/v1/auth/health

# Ticket service
curl http://localhost:8000/api/v1/tickets/health

# Team service
curl http://localhost:8000/api/v1/team/health

# All should return: {"status": "healthy"}
```

---

## Performance Testing

### Load Test Single Service
```bash
# Install Apache Bench
apt-get install apache2-utils

# Test auth service
ab -n 1000 -c 10 http://localhost:8001/health

# -n 1000: 1000 requests
# -c 10: 10 concurrent connections
```

### Monitor Resource Usage
```bash
# Real-time stats
docker stats

# Check specific service
docker stats auth-service
```

### Check Response Times
```bash
time curl http://localhost:8001/health

# Should be < 100ms
```

---

## Debugging Tips

### Enable Debug Logging
Add to service environment in docker-compose:
```yaml
environment:
  LOG_LEVEL: DEBUG
```

Then restart:
```bash
docker compose -f docker-compose.microservices.yml restart <service-name>
```

### Interactive Shell in Container
```bash
docker exec -it auth-service /bin/bash

# Then inside container:
python -c "import jose; print('jose OK')"
python -c "import passlib; print('passlib OK')"
```

### Check Environment Variables
```bash
docker exec auth-service env | grep -E "DATABASE_URL|JWT_SECRET"
```

### Rebuild Single Service
```bash
docker compose -f docker-compose.microservices.yml up -d --build auth-service
```

---

## Expected Results

### After Successful Build

**Container Status**:
```
✓ devops-tickets-postgres    - running
✓ devops-tickets-redis        - running
✓ kong-database               - running
✓ kong-gateway                - running
✓ devops-tickets-rabbitmq     - running
✓ auth-service                - running
✓ ticket-service              - running
✓ team-service                - running
✓ sla-service                 - running
✓ workload-service            - running
✓ analytics-service           - running
✓ escalation-service          - running
✓ collaboration-service       - running
✓ integration-service         - running
✓ scheduling-service          - running
✓ work-session-service        - running
```

**Health Checks**:
```
✓ PostgreSQL is ready
✓ Redis is ready
✓ Kong Admin API is accessible
✓ RabbitMQ is ready
✓ All 11 microservices health endpoints responding
```

**Logs Should Show**:
```
✅ Auth Service started successfully on port 8001
✅ Ticket Service started successfully on port 8002
... (for all services)
```

---

## Common Error Messages and Solutions

### "ModuleNotFoundError: No module named 'jose'"

**Cause**: Missing python-jose in requirements.txt

**Solution**:
```bash
# Already fixed in latest commit
git pull
docker compose -f docker-compose.microservices.yml up -d --build
```

---

### "could not connect to server: Connection refused"

**Cause**: PostgreSQL not ready yet

**Solution**: Wait 30 seconds and check again
```bash
sleep 30
docker exec devops-tickets-postgres pg_isready -U devops_user
```

---

### "Address already in use"

**Cause**: Port conflict

**Solution**: Stop conflicting service
```bash
# Check what's using the port
lsof -i :8001

# Stop old docker containers
docker compose -f ../docker-compose.yml down
```

---

### "Exec format error"

**Cause**: Wrong architecture (ARM vs x86)

**Solution**: Rebuild for your architecture
```bash
docker compose -f docker-compose.microservices.yml build --no-cache
```

---

## Quick Reference

### Start Everything
```bash
./build-and-test.sh
./setup-kong-routes.sh
./setup-kong-cors.sh
```

### Check Status
```bash
./check-status.sh
```

### Analyze Problems
```bash
./analyze-logs.sh
```

### Stop Everything
```bash
docker compose -f docker-compose.microservices.yml down
```

### Restart Single Service
```bash
docker compose -f docker-compose.microservices.yml restart sla-service
```

### View Logs
```bash
docker logs -f sla-service
```

### Clean Everything (CAUTION: Deletes data)
```bash
docker compose -f docker-compose.microservices.yml down -v
```

---

## Success Criteria

Your deployment is successful when:

- [x] `./build-and-test.sh` shows "ALL TESTS PASSED"
- [x] `./check-status.sh` shows all services with ✓
- [x] `./analyze-logs.sh` shows "No critical errors found"
- [x] All health endpoints return healthy status
- [x] Can access Kong at http://localhost:8000
- [x] Can access RabbitMQ UI at http://localhost:15672
- [x] Frontend can connect and make API calls

---

## Next Steps After Successful Testing

1. **Configure Frontend**:
   ```bash
   cd ../frontend
   echo "VITE_API_BASE_URL=http://localhost:8000" > .env
   npm install
   npm run dev
   ```

2. **Create Initial Admin User**:
   ```bash
   # Through API or database
   ```

3. **Test Complete Workflow**:
   - Login through frontend
   - Create a ticket
   - Assign to team member
   - Test all features

4. **Set Up Monitoring** (Optional):
   - Prometheus + Grafana
   - ELK Stack for logs
   - Sentry for error tracking

---

## Support

If you encounter issues:

1. Run `./analyze-logs.sh` and check for errors
2. Review DEPENDENCY_FIXES.md
3. Check AUDIT_REPORT.md
4. Review service logs: `docker logs <service-name>`

---

**All scripts tested and ready to use!** 🚀

Run `./build-and-test.sh` to start.

---

*Last Updated: 2025-01-15*
*All testing scripts completed*
