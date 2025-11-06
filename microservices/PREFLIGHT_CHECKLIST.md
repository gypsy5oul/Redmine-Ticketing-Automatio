# Pre-Flight Checklist

## Quick Status Check

Run this validation script to check if everything is ready:

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices
./validate-setup.sh
```

## Manual Checklist

### ✅ Prerequisites (COMPLETED)

- [x] **PostgreSQL running** - `devops-tickets-db` container from old app
- [x] **Redis running** - `devops-tickets-redis` container from old app
- [x] **devops-network exists** - `redmine-automation-v3_devops-network`

### 📋 Configuration Files

Check these files exist:

```bash
# In microservices/ directory
ls -la docker-compose.microservices.yml
ls -la .env
ls -la setup-kong-routes.sh
ls -la setup-kong-cors.sh
ls -la start-all.sh

# In production-services/ directory (11 services)
ls -la production-services/*/Dockerfile
ls -la production-services/*/requirements.txt

# In frontend/ directory
ls -la ../frontend/Dockerfile.microservices
ls -la ../frontend/nginx.microservices.conf
```

### 🔍 Verify Configuration

1. **Check docker-compose file is valid:**
   ```bash
   cd /home/user/Redmine-Ticketing-Automatio/microservices
   docker-compose -f docker-compose.microservices.yml config --quiet
   echo $?  # Should output: 0
   ```

2. **Check postgres and redis are accessible:**
   ```bash
   # Check postgres is on devops-network
   docker network inspect redmine-automation-v3_devops-network | grep devops-tickets-db

   # Check redis is on devops-network
   docker network inspect redmine-automation-v3_devops-network | grep devops-tickets-redis

   # Check containers are healthy
   docker ps | grep devops-tickets-db
   docker ps | grep devops-tickets-redis
   ```

3. **Check .env file has required variables:**
   ```bash
   cd /home/user/Redmine-Ticketing-Automatio/microservices
   grep DATABASE_URL .env
   grep JWT_SECRET_KEY .env
   grep SECRET_KEY .env
   grep REDMINE_API_KEY .env
   ```

### 🚀 Ready to Start

If all checks pass, you're ready to start the microservices:

**Option A - Automated (Recommended):**
```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices
./start-all.sh
```

**Option B - Manual:**
```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices

# 1. Start all microservices
docker-compose -f docker-compose.microservices.yml up -d

# 2. Wait for services to start (30-60 seconds)
sleep 30

# 3. Check all containers are running
docker-compose -f docker-compose.microservices.yml ps

# 4. Setup Kong routes
./setup-kong-routes.sh

# 5. Setup Kong CORS
./setup-kong-cors.sh

# 6. Verify services are healthy
docker ps
```

### 📊 Expected Containers

After startup, you should have these containers running:

**From old app (should already be running):**
1. `devops-tickets-db` - PostgreSQL with your data
2. `devops-tickets-redis` - Redis cache

**From microservices docker-compose:**
3. `kong-database` - Kong's PostgreSQL database
4. `kong-migrations` - Kong migrations (exits after completion)
5. `kong-gateway` - Kong API Gateway
6. `devops-tickets-rabbitmq` - RabbitMQ message queue
7. `auth-service` - Authentication & Authorization
8. `ticket-service` - Ticket management
9. `team-service` - Team management
10. `sla-service` - SLA tracking
11. `workload-service` - Workload management
12. `analytics-service` - Analytics & reporting
13. `escalation-service` - Escalation handling
14. `collaboration-service` - Collaboration features
15. `integration-service` - Redmine integration
16. `scheduling-service` - Scheduling & shifts
17. `work-session-service` - Work time tracking
18. `devops-tickets-frontend` - React frontend

**Total: 18 containers (17 running + 1 exited)**

### 🔗 Access Points

After successful startup:

- **Frontend:** http://localhost:3000
- **Kong API Gateway:** http://localhost:8000
- **Kong Admin API:** http://localhost:8444
- **RabbitMQ Management:** http://localhost:15672
  - Username: `devops_user`
  - Password: `devops_password_change_this`

### ✅ Verification Tests

Test that everything is working:

```bash
# Test Kong is accessible
curl http://localhost:8000

# Test auth service through Kong
curl http://localhost:8000/api/auth/health

# Test ticket service through Kong
curl http://localhost:8000/api/tickets/health

# Test frontend is accessible
curl http://localhost:3000

# View logs of a specific service
docker-compose -f docker-compose.microservices.yml logs auth-service

# View all logs
docker-compose -f docker-compose.microservices.yml logs
```

### ⚠️ Common Issues

**Issue: "network not found"**
```bash
# Create the network manually
docker network create redmine-automation-v3_devops-network

# Restart postgres and redis to join the network
cd /home/user/Redmine-Ticketing-Automatio
docker-compose restart postgres redis
```

**Issue: Services can't connect to postgres**
```bash
# Check postgres is on the correct network
docker network inspect redmine-automation-v3_devops-network | grep devops-tickets-db

# If not, restart postgres
cd /home/user/Redmine-Ticketing-Automatio
docker-compose restart postgres
```

**Issue: Kong routes not working**
```bash
# Re-run Kong setup scripts
cd /home/user/Redmine-Ticketing-Automatio/microservices
./setup-kong-routes.sh
./setup-kong-cors.sh
```
