# Step-by-Step Microservices Migration Guide

## 🎯 Goal
Migrate from monolithic `main.py` (3,049 lines) to 8 independent microservices without breaking existing functionality.

---

## 📋 Prerequisites

### 1. Install Required Tools
```bash
# Install Docker Compose v2
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker compose version
```

### 2. Backup Current System
```bash
# Backup database
docker exec devops-tickets-db pg_dump -U devops_user devops_tickets > backup_$(date +%Y%m%d).sql

# Backup current code
cd /path/to/project
git checkout -b backup-before-microservices
git add .
git commit -m "Backup before microservices migration"
```

---

## 🚀 Phase 1: Setup Infrastructure (Day 1)

### Step 1.1: Create Microservices Directory
```bash
cd /home/user/Redmine-Ticketing-Automatio

# Directory structure already created in microservices/
ls -la microservices/
```

### Step 1.2: Start RabbitMQ (Message Queue)
```bash
cd microservices

# Start just RabbitMQ first
docker compose -f docker-compose.microservices.yml up -d rabbitmq

# Verify RabbitMQ is running
docker logs devops-tickets-rabbitmq

# Access RabbitMQ Management UI
# http://localhost:15672
# Default credentials: devops / devops_password
```

### Step 1.3: Configure Kong API Gateway
```bash
# Start Kong database
docker compose -f docker-compose.microservices.yml up -d kong-database

# Wait for database to be ready
sleep 10

# Run Kong migrations
docker compose -f docker-compose.microservices.yml up kong-migrations

# Start Kong
docker compose -f docker-compose.microservices.yml up -d kong

# Verify Kong is running
curl http://localhost:8001

# Apply Kong configuration
curl -i -X POST http://localhost:8001/config \
  --form config=@api-gateway/kong-config.yml
```

---

## 🔧 Phase 2: Extract First Service - Team Service (Days 2-3)

### Step 2.1: Build Team Service
```bash
cd microservices/services/team-service

# Build Docker image
docker build -t team-service:latest .

# Or use docker-compose
cd ../..
docker compose -f docker-compose.microservices.yml build team-service
```

### Step 2.2: Start Team Service
```bash
# Start team-service
docker compose -f docker-compose.microservices.yml up -d team-service

# Check logs
docker logs -f team-service

# Test health check
curl http://localhost:8103/health
```

### Step 2.3: Configure Kong Route
```bash
# Add Team Service to Kong
curl -i -X POST http://localhost:8001/services \
  --data "name=team-service" \
  --data "url=http://team-service:8103"

# Add route
curl -i -X POST http://localhost:8001/services/team-service/routes \
  --data "paths[]=/api/v1/team" \
  --data "strip_path=false"

# Test through API Gateway
curl http://localhost:8000/api/v1/team/members
```

### Step 2.4: Update Frontend to Use API Gateway
```bash
# Frontend should now call API Gateway instead of direct backend
# Update VITE_API_BASE_URL to point to Kong (port 8000)
```

### Step 2.5: Verify Team Endpoints Work
```bash
# Test all team endpoints through API Gateway

# 1. Get all team members
curl -X GET http://localhost:8000/api/v1/team/members \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 2. Get specific member
curl -X GET http://localhost:8000/api/v1/team/members/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 3. Create team member
curl -X POST http://localhost:8000/api/v1/team/members \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "redmine_user_id": 123,
    "name": "John Doe",
    "email": "john@example.com",
    "team_level": "L2",
    "max_tickets": 5
  }'

# 4. Update team member
curl -X PUT http://localhost:8000/api/v1/team/members/1 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "max_tickets": 10
  }'

# 5. Get performance
curl -X GET http://localhost:8000/api/v1/team/members/1/performance \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Step 2.6: Remove Team Endpoints from main.py
```bash
cd ../../../backend/app

# Comment out or remove team endpoints from main.py
# Lines: 2264-2961 (team-related endpoints)

# Restart monolith
docker compose -f ../../docker-compose.yml restart backend
```

---

## 🎫 Phase 3: Extract Ticket Service (Days 4-5)

### Step 3.1: Create Ticket Service Structure
```bash
cd microservices/services

# Copy team-service as template
cp -r team-service ticket-service

# Update files:
# - main.py: Extract ticket endpoints from main.py
# - Update port to 8102
# - Add inter-service calls to team-service
```

### Step 3.2: Extract Ticket Endpoints from main.py

Create `ticket-service/main.py` with these endpoints:
```python
# Endpoints to extract:
# GET    /api/v1/tickets (line 252)
# POST   /api/v1/tickets/process (line 730)
# POST   /api/v1/tickets/{ticket_id}/resolve (line 769)
# GET    /api/v1/tickets/{ticket_id} (line 882)
# PUT    /api/v1/tickets/{ticket_id} (line 922)
# GET    /api/v1/tickets/{ticket_id}/comments (line 1012)
# POST   /api/v1/tickets/{ticket_id}/comments (line 1079)
# PUT    /api/v1/comments/{comment_id} (line 1159)
# DELETE /api/v1/comments/{comment_id} (line 1208)
```

### Step 3.3: Handle Inter-Service Communication

In ticket-service, when you need team member info:
```python
from shared.service_client import TeamServiceClient

# In your endpoint
team_client = TeamServiceClient(
    base_url="http://team-service:8103",
    service_token=SERVICE_TOKEN
)

# Get team member
member = await team_client.get_member(member_id)
```

### Step 3.4: Deploy Ticket Service
```bash
cd microservices
docker compose -f docker-compose.microservices.yml build ticket-service
docker compose -f docker-compose.microservices.yml up -d ticket-service

# Test
curl http://localhost:8102/health
curl http://localhost:8000/api/v1/tickets
```

---

## 📊 Phase 4: Extract Remaining Services (Days 6-10)

Repeat the same process for:

### Day 6-7: SLA Service
```bash
# Extract endpoints (lines 1251-1456 in main.py)
# Port: 8104
```

### Day 7-8: Workload Service
```bash
# Extract endpoints (lines 1468-1504 in main.py)
# Port: 8105
```

### Day 8-9: Analytics Service
```bash
# Extract endpoints (lines 1665-2231 in main.py)
# Port: 8106
```

### Day 9-10: Escalation & Integration Services
```bash
# Escalation: Port 8107
# Integration: Port 8108
```

---

## ✅ Phase 5: Testing & Validation (Days 11-12)

### Step 5.1: End-to-End Testing
```bash
# Run full test suite
pytest microservices/tests/

# Test all endpoints through API Gateway
./microservices/tests/test_all_endpoints.sh
```

### Step 5.2: Load Testing
```bash
# Install load testing tool
pip install locust

# Run load test
locust -f microservices/tests/load_test.py --host=http://localhost:8000
```

### Step 5.3: Monitor Performance
```bash
# Check service health
for port in 8101 8102 8103 8104 8105 8106 8107 8108; do
  echo "Checking service on port $port"
  curl http://localhost:$port/health
done

# Check Kong metrics
curl http://localhost:8001/metrics

# Check RabbitMQ queues
curl -u devops:devops_password http://localhost:15672/api/queues
```

---

## 🔄 Phase 6: Gradual Rollout (Days 13-14)

### Step 6.1: Use Feature Flags
```python
# In frontend or API Gateway
USE_MICROSERVICES = os.getenv("USE_MICROSERVICES", "false")

if USE_MICROSERVICES == "true":
    api_base = "http://localhost:8000"  # API Gateway
else:
    api_base = "http://localhost:8000"  # Old monolith
```

### Step 6.2: Route 10% Traffic to Microservices
```bash
# Configure Kong to route 10% traffic to new services
# 90% to old monolith
curl -X POST http://localhost:8001/services/team-service/plugins \
  --data "name=traffic-split" \
  --data "config.weights.new=10" \
  --data "config.weights.old=90"
```

### Step 6.3: Monitor Errors
```bash
# Watch error logs
docker compose -f docker-compose.microservices.yml logs -f | grep ERROR

# If errors > threshold, rollback
# Else, increase traffic to 50%, then 100%
```

---

## 🎉 Phase 7: Complete Migration (Day 15)

### Step 7.1: Route 100% Traffic to Microservices
```bash
# Update Kong to route all traffic to microservices
curl -X PATCH http://localhost:8001/services/team-service/plugins/PLUGIN_ID \
  --data "config.weights.new=100" \
  --data "config.weights.old=0"
```

### Step 7.2: Decommission Monolith main.py
```bash
# Stop old backend
docker compose -f docker-compose.yml stop backend

# Remove old endpoints from main.py
cd backend/app
# Delete lines 252-2961 from main.py

# Keep only:
# - Health check
# - Info endpoints
# - WebSocket (if needed)
```

### Step 7.3: Update Documentation
```bash
# Update API documentation
# Update deployment docs
# Update architecture diagrams
```

---

## 🚨 Rollback Plan

If anything goes wrong:

### Quick Rollback
```bash
# Stop all microservices
docker compose -f microservices/docker-compose.microservices.yml down

# Restart monolith
docker compose -f docker-compose.yml up -d backend

# Point frontend back to monolith
# Update VITE_API_BASE_URL
```

### Partial Rollback
```bash
# Rollback specific service
docker compose -f docker-compose.microservices.yml stop team-service

# Update Kong to route that path back to monolith
curl -X DELETE http://localhost:8001/services/team-service/routes/ROUTE_ID
```

---

## 📈 Success Metrics

Track these metrics during migration:

```bash
# Response time
# - Before: avg 200ms
# - Target: < 200ms

# Error rate
# - Before: 0.1%
# - Target: < 0.5%

# Throughput
# - Before: 100 req/sec
# - Target: >= 100 req/sec

# Database connections
# Monitor that we don't exhaust connection pool

# Memory usage
# Each service should use < 512MB
```

---

## 🔍 Debugging Tips

### Check Service Logs
```bash
# Individual service
docker logs -f team-service

# All services
docker compose -f docker-compose.microservices.yml logs -f

# Filter errors
docker compose -f docker-compose.microservices.yml logs | grep ERROR
```

### Check Inter-Service Communication
```bash
# Exec into a service
docker exec -it team-service /bin/sh

# Test calling another service
curl http://ticket-service:8102/health

# Check DNS resolution
nslookup ticket-service
```

### Database Connection Issues
```bash
# Check if services can reach database
docker exec -it team-service /bin/sh
psql -h postgres -U devops_user -d devops_tickets

# Check connection pool
# In service code, add logging for pool stats
```

---

## 📚 Next Steps After Migration

1. **Database per Service** - Move each service to its own database
2. **Event-Driven Architecture** - Use RabbitMQ for async communication
3. **Service Mesh** - Consider Istio for advanced routing
4. **Observability** - Add distributed tracing (Jaeger)
5. **CI/CD per Service** - Independent deployments
6. **Auto-scaling** - Scale services based on load

---

## 🎯 Timeline Summary

| Phase | Days | Activities |
|-------|------|------------|
| Phase 1 | 1 | Infrastructure setup |
| Phase 2 | 2-3 | Extract Team Service |
| Phase 3 | 2 | Extract Ticket Service |
| Phase 4 | 4-5 | Extract remaining services |
| Phase 5 | 2 | Testing & validation |
| Phase 6 | 2 | Gradual rollout |
| Phase 7 | 1 | Complete migration |
| **Total** | **15 days** | **Full migration** |

---

**Good luck with your microservices migration! 🚀**
