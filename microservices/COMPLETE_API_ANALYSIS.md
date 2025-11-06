# Complete API Analysis - Frontend to Backend Mapping

## Executive Summary

**Total API Endpoints:** 55+
**Frontend API Calls:** 65+ methods
**Backend Services:** 17 service classes
**Database Models:** 11 models
**Frontend Pages:** 11 pages

## 🎯 Microservices Breakdown (Option B - Full Independence)

### Service 1: **Auth & User Service** (Port 8001)
**Purpose:** Authentication, authorization, user management

**Endpoints:**
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- GET /api/v1/auth/me
- POST /api/v1/users (admin)
- PUT /api/v1/users/{id} (admin)

**Dependencies to Duplicate:**
- `app/models/user.py` - User model
- `app/core/security.py` - JWT, password hashing
- `app/services/user_service.py` - User CRUD
- Database: `users` table

**Frontend Pages Using:**
- Login.tsx
- All pages (auth check)

---

### Service 2: **Team Service** (Port 8003)
**Purpose:** Team member management, skills, performance

**Endpoints:**
- GET /api/v1/team/members
- GET /api/v1/team/members/{id}
- POST /api/v1/team/members
- PUT /api/v1/team/members/{id}
- DELETE /api/v1/team/members/{id}
- GET /api/v1/team/members/{id}/performance
- GET /api/v1/team/skills
- POST /api/v1/team/skills

**Dependencies to Duplicate:**
- `app/models/team.py` - TeamMember model
- `app/models/ticket.py` - TicketHistory (for performance calc)
- `app/models/performance.py` - Performance metrics
- `app/services/performance_tracker.py` - Performance calculations
- Database: `team_members`, `ticket_history`, `performance_metrics` tables

**Frontend Pages Using:**
- TeamManagement.tsx
- MemberPerformance.tsx
- Dashboard.tsx (team stats)

**Inter-Service Calls Needed:**
- → Ticket Service: Get tickets for performance metrics

---

### Service 3: **Ticket Service** (Port 8002)
**Purpose:** Core ticket management, comments, processing

**Endpoints:**
- GET /api/v1/tickets
- GET /api/v1/tickets/{id}
- POST /api/v1/tickets/process
- PUT /api/v1/tickets/{id}
- POST /api/v1/tickets/{id}/resolve
- GET /api/v1/tickets/{id}/comments
- POST /api/v1/tickets/{id}/comments
- PUT /api/v1/comments/{id}
- DELETE /api/v1/comments/{id}

**Dependencies to Duplicate:**
- `app/models/ticket.py` - TicketHistory, TicketComment, TicketCollaboration
- `app/models/filter.py` - SavedTicketFilter
- `app/services/ticket_processor.py` - Full ticket processing pipeline
- `app/services/redmine_service.py` - Redmine API integration
- `app/services/llm_service.py` - AI ticket analysis
- `app/services/ml_service.py` - ML predictions (category, complexity, resolution time)
- Database: `ticket_history`, `ticket_comments`, `ticket_collaboration`, `saved_filters` tables

**Frontend Pages Using:**
- TicketMonitoring.tsx
- Dashboard.tsx
- CollaborationWorkspace.tsx

**Inter-Service Calls Needed:**
- → Team Service: Get team member info
- → SLA Service: Get SLA status for tickets
- → Work Session Service: Get active sessions
- ← Redmine (External): Sync with Redmine

---

### Service 4: **SLA Service** (Port 8004)
**Purpose:** SLA policy management, tracking, breach detection

**Endpoints:**
- GET /api/v1/sla/policies
- POST /api/v1/sla/policies
- PUT /api/v1/sla/policies/{id}
- GET /api/v1/sla/status/{ticket_id}
- GET /api/v1/sla/at-risk
- POST /api/v1/sla/{ticket_id}/pause
- POST /api/v1/sla/{ticket_id}/resume

**Dependencies to Duplicate:**
- `app/models/sla.py` - SLAPolicy, SLATracker, SLABreach
- `app/models/business_hours.py` - Business hours config
- `app/services/sla_manager.py` - SLA calculations, tracking
- Database: `sla_policies`, `sla_trackers`, `sla_breaches`, `business_hours` tables

**Frontend Pages Using:**
- SLAConfiguration.tsx
- Dashboard.tsx (SLA metrics)
- TicketMonitoring.tsx (SLA status per ticket)

**Inter-Service Calls Needed:**
- → Ticket Service: Get ticket details for SLA calculation
- ← Events: Listen to ticket creation/assignment

---

### Service 5: **Workload Service** (Port 8005)
**Purpose:** Capacity tracking, load balancing, alerts

**Endpoints:**
- GET /api/v1/workload
- GET /api/v1/workload/capacity
- GET /api/v1/workload/alerts

**Dependencies to Duplicate:**
- `app/services/workload_manager.py` - Workload calculations
- `app/models/team.py` - TeamMember (for capacity)
- `app/models/ticket.py` - TicketHistory (for current workload)
- Database: Queries `team_members`, `ticket_history`

**Frontend Pages Using:**
- Dashboard.tsx
- TeamManagement.tsx

**Inter-Service Calls Needed:**
- → Team Service: Get team member data
- → Ticket Service: Get active tickets per member

---

### Service 6: **Escalation Service** (Port 8007)
**Purpose:** Manual/auto escalation, escalation history

**Endpoints:**
- POST /api/v1/escalation/{ticket_id}/manual
- GET /api/v1/escalation/{ticket_id}/check
- GET /api/v1/escalation/{ticket_id}/history

**Dependencies to Duplicate:**
- `app/models/escalation.py` - Escalation model
- `app/services/escalation_service.py` - Escalation logic
- Database: `escalations` table

**Frontend Pages Using:**
- TicketMonitoring.tsx
- Dashboard.tsx

**Inter-Service Calls Needed:**
- → Ticket Service: Update ticket assignment after escalation
- → Team Service: Find next level team members
- → Notification Service: Send escalation alerts

---

### Service 7: **Collaboration Service** (Port 8008)
**Purpose:** Multi-member ticket collaboration

**Endpoints:**
- POST /api/v1/collaboration/{ticket_id}/add
- DELETE /api/v1/collaboration/{ticket_id}/remove/{member_id}
- GET /api/v1/collaboration/{ticket_id}

**Dependencies to Duplicate:**
- `app/models/ticket.py` - TicketCollaboration model
- `app/services/collaboration_service.py` - Collaboration logic
- Database: `ticket_collaboration` table

**Frontend Pages Using:**
- CollaborationWorkspace.tsx
- TicketMonitoring.tsx

**Inter-Service Calls Needed:**
- → Ticket Service: Get ticket details
- → Team Service: Validate team members

---

### Service 8: **Analytics & ML Service** (Port 8006)
**Purpose:** ML predictions, forecasting, dashboards, performance

**Endpoints:**
- GET /api/v1/analytics/forecast
- GET /api/v1/analytics/sla-prediction/{ticket_id}
- GET /api/v1/analytics/team-performance
- POST /api/v1/ml/train
- GET /api/v1/ml/models/status
- POST /api/v1/ml/predict/category
- POST /api/v1/ml/predict/complexity
- POST /api/v1/ml/predict/resolution-time
- POST /api/v1/ml/predict/all
- GET /api/v1/dashboard/metrics
- GET /api/v1/dashboard/activity

**Dependencies to Duplicate:**
- `app/services/ml_service.py` - ML models (scikit-learn)
- `app/services/llm_service.py` - LLM integration
- `app/services/performance_tracker.py` - Performance metrics
- `app/services/activity_tracker.py` - Activity logging
- `app/models/performance.py` - Performance models
- `app/models/activity.py` - Activity models
- Database: `performance_metrics`, `activities`, ML model files

**Frontend Pages Using:**
- Analytics.tsx
- Dashboard.tsx
- MemberPerformance.tsx

**Inter-Service Calls Needed:**
- → Ticket Service: Get historical ticket data for training
- → Team Service: Get team performance data
- → SLA Service: Get SLA compliance data

---

### Service 9: **Work Session Service** (Port 8011)
**Purpose:** Track active work time vs waiting time

**Endpoints:**
- POST /api/v1/tickets/{ticket_id}/work/start
- POST /api/v1/tickets/{ticket_id}/work/pause
- POST /api/v1/tickets/{ticket_id}/work/resume
- GET /api/v1/tickets/{ticket_id}/work/summary
- GET /api/v1/work/active

**Dependencies to Duplicate:**
- `app/models/work_session.py` - WorkSession model
- `app/services/work_session_service.py` - Session tracking
- Database: `work_sessions` table

**Frontend Pages Using:**
- TicketMonitoring.tsx
- Dashboard.tsx

**Inter-Service Calls Needed:**
- → Ticket Service: Update ticket work metrics
- ← Events: Listen to ticket status changes

---

### Service 10: **Scheduling Service** (Port 8010)
**Purpose:** Shifts, leaves, on-call rotation

**Endpoints:**
- GET /api/v1/shifts
- POST /api/v1/shifts
- PUT /api/v1/shifts/{id}
- DELETE /api/v1/shifts/{id}
- GET /api/v1/leaves
- GET /api/v1/leaves/me
- POST /api/v1/leaves
- PUT /api/v1/leaves/{id}
- DELETE /api/v1/leaves/{id}
- POST /api/v1/leaves/{id}/status
- GET /api/v1/oncall/assignments
- POST /api/v1/oncall/assignments/run
- GET /api/v1/oncall/rotate
- POST /api/v1/oncall/assignments/{id}/replace

**Dependencies to Duplicate:**
- `app/models/schedule.py` - ShiftAssignment, MemberLeave, OncallRotation
- `app/services/scheduling_service.py` - Scheduling logic
- Database: `shift_assignments`, `member_leaves`, `oncall_rotations` tables

**Frontend Pages Using:**
- Scheduling.tsx

**Inter-Service Calls Needed:**
- → Team Service: Get team members for scheduling

---

### Service 11: **Integration Service** (Port 8009)
**Purpose:** External integrations (Redmine, Notifications, Projects)

**Endpoints:**
- GET /api/v1/redmine/group-members
- GET /api/v1/redmine/user/{user_id}
- POST /api/v1/redmine/sync-statuses
- GET /api/v1/projects
- GET /api/v1/projects/{project_jira_id}
- GET /api/v1/activities
- GET /api/v1/activities/ticket/{ticket_id}
- GET /api/v1/scheduler/status

**Dependencies to Duplicate:**
- `app/services/redmine_service.py` - Redmine API
- `app/services/notification_service.py` - Google Chat, Slack
- `app/services/project_service.py` - Project analytics
- `app/services/activity_tracker.py` - Activity logging
- `app/models/activity.py` - Activity model
- Database: `activities`, `projects` tables

**Frontend Pages Using:**
- Projects.tsx
- ProjectDetail.tsx
- Dashboard.tsx

**Inter-Service Calls Needed:**
- ← Redmine (External): Sync data
- → Ticket Service: Create tickets from Redmine
- → Team Service: Sync team members

---

## 📊 Database Schema per Service

### Auth Service Database
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    email VARCHAR(200) UNIQUE,
    hashed_password VARCHAR(200),
    full_name VARCHAR(200),
    role VARCHAR(20),
    active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Team Service Database
```sql
CREATE TABLE team_members (
    id SERIAL PRIMARY KEY,
    redmine_user_id INTEGER UNIQUE,
    name VARCHAR(200),
    email VARCHAR(200),
    team_level VARCHAR(10),
    max_tickets INTEGER,
    skills JSONB,
    active BOOLEAN,
    user_id INTEGER  -- Link to Auth Service user
);
```

### Ticket Service Database
```sql
CREATE TABLE ticket_history (
    id SERIAL PRIMARY KEY,
    redmine_ticket_id INTEGER UNIQUE,
    subject VARCHAR(500),
    description TEXT,
    priority VARCHAR(50),
    status VARCHAR(50),
    category VARCHAR(50),
    complexity VARCHAR(50),
    assigned_to_id INTEGER,  -- Team Service member ID
    team_level VARCHAR(10),
    requester_name VARCHAR(255),
    sla_breached BOOLEAN,
    created_at TIMESTAMP,
    resolved_at TIMESTAMP,
    -- Work tracking
    total_work_minutes INTEGER,
    total_waiting_minutes INTEGER,
    work_efficiency_percent FLOAT
);

CREATE TABLE ticket_comments (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES ticket_history(id),
    content TEXT,
    author_id INTEGER,  -- Auth Service user ID
    comment_type VARCHAR(20),
    created_at TIMESTAMP
);
```

### SLA Service Database
```sql
CREATE TABLE sla_policies (
    id SERIAL PRIMARY KEY,
    priority VARCHAR(50),
    response_time_minutes INTEGER,
    resolution_time_minutes INTEGER,
    environment VARCHAR(50),
    business_hours_only BOOLEAN
);

CREATE TABLE sla_trackers (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER UNIQUE,  -- Ticket Service ticket ID
    policy_id INTEGER REFERENCES sla_policies(id),
    status VARCHAR(50),
    response_deadline TIMESTAMP,
    resolution_deadline TIMESTAMP,
    paused BOOLEAN,
    created_at TIMESTAMP
);
```

## 🔗 Inter-Service Communication Matrix

| Service | Calls → | Called By ← | Communication Type |
|---------|---------|-------------|-------------------|
| **Auth** | - | All services | Sync (JWT validation) |
| **Team** | - | Ticket, Workload, Analytics, Scheduling | Sync (HTTP) |
| **Ticket** | Team, SLA, Work Session | Analytics, Escalation | Sync + Events |
| **SLA** | Ticket | Ticket, Dashboard | Sync + Events |
| **Workload** | Team, Ticket | Dashboard | Sync |
| **Escalation** | Ticket, Team, Notification | Scheduler | Async (Events) |
| **Collaboration** | Ticket, Team | Ticket UI | Sync |
| **Analytics** | Ticket, Team, SLA | Dashboard | Sync |
| **Work Session** | Ticket | Ticket, Dashboard | Sync + Events |
| **Scheduling** | Team | Dashboard | Sync |
| **Integration** | Team, Ticket | Scheduler | Async (Cron) |

## 🎯 Implementation Strategy (Option B)

### Phase 1: Foundational Services (Week 1-2)
1. **Auth Service** - Must be first (everyone depends on it)
2. **Team Service** - Second (many services need team data)

### Phase 2: Core Business Services (Week 3-4)
3. **Ticket Service** - Largest, most complex
4. **SLA Service** - Depends on Ticket
5. **Work Session Service** - Depends on Ticket

### Phase 3: Secondary Services (Week 5-6)
6. **Workload Service**
7. **Escalation Service**
8. **Collaboration Service**
9. **Scheduling Service**

### Phase 4: Analytics & Integration (Week 7-8)
10. **Analytics & ML Service** - Needs historical data
11. **Integration Service** - External APIs

### Phase 5: Testing & Deployment (Week 9-10)
- End-to-end testing
- Load testing
- Gradual rollout
- Production deployment

---

## 🔧 Technology Stack per Service

### All Services Share:
- **Framework:** FastAPI
- **Database:** PostgreSQL (own schema/database)
- **Cache:** Redis (shared initially, can split later)
- **Auth:** JWT (validate tokens, no shared session)
- **Logging:** Loguru → ELK Stack
- **Monitoring:** Prometheus + Grafana
- **Tracing:** Jaeger (distributed tracing)

### Service-Specific:
- **Analytics Service:** scikit-learn, pandas, numpy
- **Integration Service:** requests (Redmine API), aiohttp
- **Work Session Service:** APScheduler (cleanup jobs)

---

## 📝 Next Steps

1. ✅ Complete analysis (DONE)
2. ⏳ Build Auth Service (foundational)
3. ⏳ Build Team Service
4. ⏳ Build Ticket Service (largest)
5. ⏳ Build remaining 8 services
6. ⏳ Set up API Gateway (Kong)
7. ⏳ Set up event bus (RabbitMQ)
8. ⏳ End-to-end testing
9. ⏳ Production deployment

**Estimated Timeline:** 10 weeks for complete migration
**Team Size:** 1-2 developers
**Risk Level:** Medium (extensive testing required)

---

**This analysis provides the blueprint for building 11 fully independent microservices.**
