# 🚀 DevOps Ticket Management System v3.0

**Enterprise-Grade Automated Ticket Assignment, AI Analysis, and Performance Tracking**

---

## ✨ What's Been Built

This is a complete rewrite of your Redmine automation tool into an enterprise-grade system with:

### ✅ **Phase 1-2: Core Infrastructure & Database (COMPLETE)**
- ✅ PostgreSQL database with comprehensive models (12 tables)
- ✅ Redis caching layer for performance
- ✅ Pydantic-based configuration management
- ✅ Production-ready database schema with relationships

### ✅ **Phase 3: Core Services (COMPLETE)**
- ✅ **SLAManager** – Real-time SLA tracking, alerting, pause/resume, breach history
- ✅ **EnhancedLLMService** – Multi-stage AI analysis with caching and async support
- ✅ **MLPredictionService** – Smart routing, forecasting, and SLA risk prediction
- ✅ **EscalationService** – Manual/assisted escalation with ML routing
- ✅ **NotificationService** – Google Chat / Slack notifications with dedupe guards
- ✅ **WorkloadManager** – Capacity calculations, cache-backed workload metrics
- ✅ **TicketProcessor** – End-to-end ingestion pipeline tying AI/ML/SLA/notifications together
- ✅ **CollaborationService** – Multi-engineer collaboration metrics and caching helpers
- ✅ Supporting services: QueryOptimizer, RedmineService, PerformanceTracker, scheduler jobs

### 📋 **Current Focus / Next Enhancements**
1. Harden authentication & authorization (JWT in `core/security.py`, RBAC for admin UI)
2. Expand automated test coverage (unit + integration) and CI pipelines
3. Production observability: structured logging exports, Prometheus dashboards, alerting
4. Deployment polish (compose profiles, environment docs, release notes) and ongoing UX refinements

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     React Admin Portal                        │
│    Dashboard | Team Mgmt | SLA Config | Analytics            │
└────────────────────┬─────────────────────────────────────────┘
                     │ REST API + WebSocket
┌────────────────────┴─────────────────────────────────────────┐
│                 FastAPI Backend (Python)                      │
├───────────────────────────────────────────────────────────────┤
│  SLAManager | MLService | LLMService | EscalationService     │
├───────────────────────────────────────────────────────────────┤
│            PostgreSQL + Redis + Background Jobs               │
└───────────────────────────────────────────────────────────────┘
```

---

## 📁 File Structure

```
./
├── backend/
│   ├── app/
│   │   ├── core/                    # Config, DB session helpers, security stubs
│   │   ├── models/                  # SQLAlchemy models (team, ticket, SLA, etc.)
│   │   ├── services/                # Business services (SLA, ML, Escalation, Notifications…)
│   │   ├── scheduler/               # APScheduler jobs (ticket processing, analytics)
│   │   ├── websocket/               # Real-time collaboration manager
│   │   ├── schemas/                 # Pydantic API schemas
│   │   └── main.py                  # FastAPI application with REST + WebSocket routes
│   ├── requirements.txt             # Backend dependencies
│   ├── .env.example                 # Sample environment configuration
│   └── Dockerfile                   # Backend container image
├── frontend/                        # React (Vite + MUI) admin portal
├── deployment/                      # Compose manifests, infra helpers
└── docs/                            # Additional implementation notes
```

---

## 🎯 Key Features Implemented

### 1. **Smart Ticket Routing** (ML-Based)
```python
# ml_service.py - smart_route_ticket()
Factors:
- 40% Skill matching (exact + related skills)
- 20% Timezone awareness (working hours preference)
- 20% Workload balancing (current capacity)
- 20% Historical performance (SLA compliance, avg resolution time)

Returns: (best_assignee, confidence_score, reasons)
```

### 2. **Enhanced LLM Analysis** (Multi-Stage)
```python
# llm_service.py - analyze_ticket()
Stage 1: Classification
  → category, complexity, estimated_hours, required_skills

Stage 2: Action Plan Generation
  → Detailed troubleshooting steps for engineer
  → Actual commands (not placeholders)

Stage 3: Customer-Facing Response
  → Professional initial response
  → Structured information requests
  → RedHat/AWS Support style
```

### 3. **SLA Management** (Enterprise-Grade)
```python
# sla_manager.py
Features:
- Real-time SLA tracking with Redis caching
- Auto-alerts at 80% (warning), 90% (critical)
- Auto-escalation on SLA deadline
- Pause/Resume for "pending customer" status
- Comprehensive breach recording
- Environment-specific SLA policies
```

### 4. **Predictive Analytics**
```python
# ml_service.py - predict_sla_breach_probability()
Risk Factors:
- Priority level
- Assignee workload
- Ticket complexity
- Historical SLA compliance

Returns: probability, risk_level, factors, recommendation
```

### 5. **Database Schema** (12 Tables)
- ✅ `team_members` - L1/L2/L3 with skills & timezones
- ✅ `skills` - Technology skills with proficiency levels
- ✅ `team_member_skills` - Many-to-many with expertise
- ✅ `ticket_history` - Complete lifecycle tracking
- ✅ `ticket_collaborations` - Multi-engineer collaboration
- ✅ `sla_policies` - Configurable SLA rules
- ✅ `sla_trackers` - Real-time SLA monitoring
- ✅ `sla_breaches` - Breach history for reporting
- ✅ `escalations` - Multi-level escalation tracking
- ✅ `performance_metrics` - Daily team metrics
- ✅ `ticket_resolution_metrics` - Per-ticket analytics
- ✅ `business_hours` - Configurable work schedules
- ✅ `users` - Admin portal authentication

---

## 🧭 Operational Readiness

All core services are online. Priorities for production hardening:

- **Security & Access Control:** Finish JWT flows in `core/security.py`, enforce role-based permissions in the React portal, and secure scheduler/websocket endpoints.
- **Automated Testing:** Expand pytest coverage across services and REST routes, track with `pytest-cov`, and wire the suite into CI.
- **Observability:** Enable Prometheus/Sentry exporters, add dashboards/alerts, and document incident-response runbooks.
- **Deployment Packaging:** Finalize Docker/Compose/Kubernetes manifests, automate Alembic migrations, and capture infrastructure prerequisites in `CONFIGURATION.txt`.

## 🗄️ Database Setup

### 1. Create Database
```bash
# PostgreSQL
createdb devops_tickets

# Redis
docker run -d -p 6379:6379 redis:latest
```

### 2. Run Migrations
```bash
cd backend
pip install -r requirements.txt

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

### 3. Seed Initial Data (optional)
```bash
cd backend
python populate_skills.py                 # loads sample skills
python backfill_performance_metrics.py    # generates demo analytics rows
```

---

## 🔧 Configuration

Edit `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/devops_tickets
REDIS_URL=redis://localhost:6379/0

# Redmine
REDMINE_BASE_URL=https://your-redmine.com
REDMINE_API_KEY=your-api-key

# LLM
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=your-model-name

# Notifications
GOOGLE_CHAT_WEBHOOK=https://chat.googleapis.com/...

# Scheduler
TICKET_PROCESSING_INTERVAL=2  # minutes
```

---

## 📊 Example Usage

### Smart Routing
```python
from app.services.ml_service import MLPredictionService
from app.services.llm_service import EnhancedLLMService

# Analyze ticket with AI
llm_service = EnhancedLLMService()
analysis = llm_service.analyze_ticket(ticket)
# → category, complexity, action_plan, customer_response

# Route to best engineer
ml_service = MLPredictionService(db)
best_assignee, confidence, reasons = ml_service.smart_route_ticket(
    ticket, available_members, analysis['classification']['category']
)
# → (engineer, 0.87, ["Strong skill match", "Currently in working hours"])
```

### SLA Tracking
```python
from app.services.sla_manager import SLAManager

sla_manager = SLAManager(db)

# Start tracking when assigned
tracker = sla_manager.start_sla_tracking(ticket_id, priority="P1(Critical)")

# Check status
status = sla_manager.get_sla_status(ticket_id)
# → {"status": "at_risk", "remaining_minutes": 45, "completion_percentage": 82}

# Pause when waiting for customer
sla_manager.pause_sla(ticket_id)

# Resume when customer responds
sla_manager.resume_sla(ticket_id)
```

---


## 🚀 Quick Start for Development

```bash
# 1. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your settings (Postgres, Redis, Redmine, LLM, notifications…)

# 3. Database
createdb devops_tickets
alembic upgrade head
python populate_skills.py        # optional helper to seed skills
python backfill_performance_metrics.py  # optional analytics seed

# 4. Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# or `docker-compose up backend` from the repository root

# 5. Frontend
cd ../frontend
npm install
npm run dev -- --host

# 6. Smoke-test
curl http://localhost:8000/health
open http://localhost:5173
```

---

## 📈 What Makes This Enterprise-Grade?

1. ✅ **Comprehensive database schema** with proper relationships
2. ✅ **ML-based smart routing** with multi-factor scoring
3. ✅ **Real-time SLA tracking** with auto-escalation
4. ✅ **Enhanced AI analysis** with professional prompts
5. ✅ **Predictive analytics** for capacity planning
6. ✅ **Multi-level escalation** (L1→L2→L3)
7. ✅ **Collaborative resolution** with real-time updates
8. ✅ **Performance tracking** and analytics
9. ✅ **Timezone-aware assignment**
10. ✅ **Skill-based routing**
11. ✅ **Configurable SLA policies**
12. ✅ **Business hours support**

---


## 📞 Support

For questions or issues:
1. Review `IMPLEMENTATION_GUIDE.md` for detailed architecture
2. Check database schema in models files
3. Test services individually before integration

---

**Built with ❤️ for enterprise DevOps automation**
