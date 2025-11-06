# Microservices Migration Plan

## Overview
Migrating from monolithic `main.py` (3,049 lines) to microservices architecture with 8 independent services.

## Current State
- **main.py**: 3,049 lines, 55 endpoints
- **Architecture**: Monolithic
- **Issues**:
  - Hard to maintain
  - Hard to scale
  - Hard to test
  - Single point of failure

## Target Architecture

### 8 Microservices
1. **Auth Service** (Port 8001) - Authentication & Authorization
2. **Ticket Service** (Port 8002) - Core ticket management
3. **Team Service** (Port 8003) - Team member management
4. **SLA Service** (Port 8004) - SLA policies and tracking
5. **Workload Service** (Port 8005) - Workload balancing
6. **Analytics Service** (Port 8006) - ML/AI and analytics
7. **Escalation Service** (Port 8007) - Escalation management
8. **Integration Service** (Port 8008) - External integrations

### Shared Infrastructure
- PostgreSQL (Shared database - will migrate to per-service DBs later)
- Redis (Shared cache)
- RabbitMQ (Message broker for async communication)
- API Gateway (Kong or Nginx)

## Service Boundaries

### Auth Service
**Endpoints (from main.py):**
- Already extracted to `app/api/v1/auth.py` ✅

**No migration needed** - already a router!

### Ticket Service
**Endpoints (from main.py):**
```
GET    /api/v1/tickets
POST   /api/v1/tickets/process
POST   /process-tickets (legacy)
POST   /api/v1/tickets/{ticket_id}/resolve
GET    /api/v1/tickets/{ticket_id}
PUT    /api/v1/tickets/{ticket_id}
GET    /api/v1/tickets/{ticket_id}/comments
POST   /api/v1/tickets/{ticket_id}/comments
PUT    /api/v1/comments/{comment_id}
DELETE /api/v1/comments/{comment_id}
```
**Lines in main.py:** ~500-1200

### Team Service
**Endpoints (from main.py):**
```
GET    /api/v1/team/members
GET    /api/v1/team/members/{member_id}
POST   /api/v1/team/members
PUT    /api/v1/team/members/{member_id}
DELETE /api/v1/team/members/{member_id}
GET    /api/v1/team/members/{member_id}/performance
GET    /api/v1/team/skills
POST   /api/v1/team/skills
```
**Lines in main.py:** ~400-700

### SLA Service
**Endpoints (from main.py):**
```
GET    /api/v1/sla/policies
POST   /api/v1/sla/policies
PUT    /api/v1/sla/policies/{policy_id}
GET    /api/v1/sla/status/{ticket_id}
GET    /api/v1/sla/at-risk
POST   /api/v1/sla/{ticket_id}/pause
POST   /api/v1/sla/{ticket_id}/resume
```
**Lines in main.py:** ~250-500

### Workload Service
**Endpoints (from main.py):**
```
GET    /api/v1/workload
GET    /api/v1/workload/capacity
GET    /api/v1/workload/alerts
```
**Lines in main.py:** ~50-100

### Analytics Service
**Endpoints (from main.py):**
```
GET    /api/v1/analytics/forecast
GET    /api/v1/analytics/sla-prediction/{ticket_id}
POST   /api/v1/ml/train
GET    /api/v1/analytics/team-performance
GET    /api/v1/ml/models/status
POST   /api/v1/ml/predict/category
POST   /api/v1/ml/predict/complexity
POST   /api/v1/ml/predict/resolution-time
POST   /api/v1/ml/predict/all
GET    /api/v1/dashboard/metrics
GET    /api/v1/dashboard/activity
```
**Lines in main.py:** ~700-1000

### Escalation Service
**Endpoints (from main.py):**
```
POST   /api/v1/escalation/{ticket_id}/manual
GET    /api/v1/escalation/{ticket_id}/check
GET    /api/v1/escalation/{ticket_id}/history
```
**Lines in main.py:** ~100-150

### Integration Service
**Endpoints (from main.py):**
```
GET    /api/v1/redmine/group-members
GET    /api/v1/redmine/user/{user_id}
POST   /api/v1/redmine/sync-statuses
```
**Lines in main.py:** ~50-100

### Collaboration Service
**Endpoints (from main.py):**
```
POST   /api/v1/collaboration/{ticket_id}/add
DELETE /api/v1/collaboration/{ticket_id}/remove/{team_member_id}
GET    /api/v1/collaboration/{ticket_id}
```
**Lines in main.py:** ~100-150

## Migration Phases

### Phase 1: Infrastructure Setup (Week 1)
- [ ] Set up RabbitMQ for message queue
- [ ] Create shared library package
- [ ] Set up API Gateway (Kong or Nginx)
- [ ] Create service template structure
- [ ] Set up Docker Compose for microservices

### Phase 2: Extract Team Service (Week 2)
- [ ] Create team-service directory
- [ ] Extract team endpoints from main.py
- [ ] Add service-to-service auth
- [ ] Deploy and test
- [ ] Update API Gateway routing

### Phase 3: Extract Ticket Service (Week 3)
- [ ] Create ticket-service directory
- [ ] Extract ticket endpoints from main.py
- [ ] Handle ticket dependencies
- [ ] Deploy and test

### Phase 4: Extract Analytics & SLA Services (Week 4)
- [ ] Extract analytics-service
- [ ] Extract sla-service
- [ ] Set up async communication for analytics

### Phase 5: Extract Remaining Services (Week 5)
- [ ] Extract workload-service
- [ ] Extract escalation-service
- [ ] Extract integration-service

### Phase 6: Testing & Optimization (Week 6)
- [ ] End-to-end testing
- [ ] Performance testing
- [ ] Load testing
- [ ] Remove old main.py endpoints
- [ ] Update documentation

## Inter-Service Communication

### Synchronous (HTTP/REST)
Use for:
- Real-time queries
- CRUD operations
- Request-response patterns

Example: Ticket Service → Team Service (get team member info)

### Asynchronous (Message Queue)
Use for:
- Event notifications
- Long-running operations
- Eventually consistent operations

Example: Ticket Created → Analytics Service (update ML models)

## Shared Libraries

Create `shared` package with:
- Database models (SQLAlchemy)
- Pydantic schemas
- Authentication utilities
- Common middleware
- Constants and enums

## Technology Stack

### Per Service
- **Framework**: FastAPI
- **Database**: PostgreSQL (shared initially, then per-service)
- **Cache**: Redis
- **Message Queue**: RabbitMQ
- **Service Discovery**: Consul (optional)

### Infrastructure
- **API Gateway**: Kong or Nginx
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK Stack
- **Tracing**: Jaeger (distributed tracing)

## Database Strategy

### Phase 1: Shared Database
All services use same PostgreSQL database (easier migration)

### Phase 2: Database per Service (Future)
Each service gets its own database schema:
- `auth_db`
- `ticket_db`
- `team_db`
- etc.

## Deployment

### Docker Compose (Development)
```yaml
services:
  auth-service:
    build: ./services/auth-service
    ports: ["8001:8001"]

  ticket-service:
    build: ./services/ticket-service
    ports: ["8002:8002"]

  # ... other services

  api-gateway:
    image: kong:latest
    ports: ["8000:8000"]
```

### Kubernetes (Production)
Each service as a Deployment + Service + Ingress

## Success Metrics

- [ ] All endpoints migrated
- [ ] No breaking changes for frontend
- [ ] Response time < 200ms (p95)
- [ ] Each service independently deployable
- [ ] Test coverage > 70% per service
- [ ] Zero downtime deployment

## Rollback Strategy

- Keep monolith running in parallel
- API Gateway routes gradually to new services
- Feature flags to toggle between old/new
- Can rollback per-service if issues arise

## Timeline

- **Week 1**: Infrastructure setup
- **Week 2**: Team Service extraction
- **Week 3**: Ticket Service extraction
- **Week 4**: Analytics & SLA Services
- **Week 5**: Remaining services
- **Week 6**: Testing & optimization
- **Week 7**: Full cutover, remove monolith

**Total: 7 weeks**

## Next Steps

1. Review and approve this plan
2. Set up infrastructure (RabbitMQ, API Gateway)
3. Create shared library package
4. Start with Team Service extraction
5. Iterate and improve

---

**Status**: Planning Phase
**Last Updated**: 2025-11-06
**Owner**: DevOps Team
