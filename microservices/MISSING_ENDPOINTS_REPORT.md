# Missing Endpoints Report - Old App vs Microservices

## Executive Summary

The microservices architecture is **MISSING CRITICAL ENDPOINTS** that exist in the old monolithic backend. This is causing:
- ❌ Dashboard not loading (no metrics data)
- ❌ Missing values across all pages
- ❌ Frontend can't fetch required data

## Critical Missing Endpoints

### 1. 🚨 DASHBOARD ENDPOINTS (HIGH PRIORITY - USER REPORTED)

**Missing from microservices:**

#### `/api/v1/dashboard/metrics` (GET)
- **Location in old app:** `/backend/app/main.py:1954-2228`
- **Returns:**
  - `total_tickets_today`: Count of tickets resolved today
  - `tickets_in_progress`: Count of open tickets
  - `sla_compliance_rate`: Percentage of tickets meeting SLA
  - `avg_resolution_time_hours`: Average time to resolve tickets
  - `at_risk_tickets`: Count of tickets at risk of SLA breach
  - `critical_tickets`: Count of P1 critical tickets
  - `team_capacity_percentage`: Team workload vs capacity
  - `active_collaborations`: Count of collaborative tickets
  - `card_insights`: 7-day sparklines and distributions for:
    - Total tickets trend
    - SLA compliance trend
    - At-risk tickets trend
    - Team capacity trend
    - Priority distribution
    - SLA status distribution
    - Capacity distribution

**Why it's critical:** This is the MAIN DASHBOARD data. Without this, the dashboard is empty.

**Recommendation:** Add to **analytics-service** since it aggregates data from multiple sources.

#### `/api/v1/dashboard/activity` (GET)
- **Location in old app:** `/backend/app/main.py:2231-2262`
- **Returns:** Recent ticket activity/changes (limit: 20)
- **Recommendation:** Add to **analytics-service** or create **activity-service**

---

### 2. TICKET ENDPOINTS (Partially Missing)

**Existing in microservices:**
- ✅ GET /api/v1/tickets (list tickets)
- ✅ GET /api/v1/tickets/{id} (get ticket details)
- ✅ PUT /api/v1/tickets/{id} (update ticket)
- ✅ POST /api/v1/tickets (create ticket)

**Missing from microservices:**

#### `/api/v1/tickets/process` (POST)
- **Location:** `/backend/app/main.py:730-749`
- **Function:** Triggers batch processing of tickets
- **Recommendation:** Add to **ticket-service**

#### `/api/v1/tickets/{ticket_id}/resolve` (POST)
- **Location:** `/backend/app/main.py:769-881`
- **Function:** Resolves a ticket with resolution notes
- **Recommendation:** Add to **ticket-service**

---

### 3. ANALYTICS & ML ENDPOINTS (Partially Missing)

**Existing:**
- ✅ GET /api/v1/analytics/* (some endpoints)
- ✅ POST /api/v1/ml/predict-* (some endpoints)

**Missing:**

#### `/api/v1/analytics/forecast` (GET)
- **Location:** `/backend/app/main.py:1665-1674`
- **Function:** Forecast ticket volume
- **Recommendation:** Verify exists in **analytics-service**

#### `/api/v1/analytics/sla-prediction/{ticket_id}` (GET)
- **Location:** `/backend/app/main.py:1676-1693`
- **Function:** Predict if ticket will breach SLA
- **Recommendation:** Verify exists in **analytics-service**

#### `/api/v1/ml/train` (POST)
- **Location:** `/backend/app/main.py:1695-1714`
- **Function:** Trigger ML model training
- **Recommendation:** Add to **analytics-service**

#### `/api/v1/analytics/team-performance` (GET)
- **Location:** `/backend/app/main.py:1716-1781`
- **Function:** Get detailed team performance metrics
- **Recommendation:** Add to **analytics-service**

#### `/api/v1/ml/models/status` (GET)
- **Location:** `/backend/app/main.py:1783-1817`
- **Function:** Get ML model status and accuracy
- **Recommendation:** Add to **analytics-service**

#### `/api/v1/ml/predict/category` (POST)
- **Location:** `/backend/app/main.py:1819-1844`
- **Function:** Predict ticket category
- **Recommendation:** Verify exists in **analytics-service**

#### `/api/v1/ml/predict/complexity` (POST)
- **Location:** `/backend/app/main.py:1846-1873`
- **Function:** Predict ticket complexity
- **Recommendation:** Add to **analytics-service**

#### `/api/v1/ml/predict/resolution-time` (POST)
- **Location:** `/backend/app/main.py:1875-1901`
- **Function:** Predict time to resolve
- **Recommendation:** Add to **analytics-service**

#### `/api/v1/ml/predict/all` (POST)
- **Location:** `/backend/app/main.py:1903-1952`
- **Function:** Run all ML predictions at once
- **Recommendation:** Add to **analytics-service**

---

### 4. ACTIVITIES/AUDIT LOG (Completely Missing)

**Missing:**

#### `/api/v1/activities` (GET)
- **Location:** `/backend/app/main.py:2928-2959`
- **Function:** Get all system activities/audit log
- **Recommendation:** Create **activity-service** OR add to **ticket-service**

#### `/api/v1/activities/ticket/{ticket_id}` (GET)
- **Location:** `/backend/app/main.py:2961-2994`
- **Function:** Get activities for specific ticket
- **Recommendation:** Create **activity-service** OR add to **ticket-service**

---

### 5. SCHEDULER ENDPOINT (Missing)

#### `/api/v1/scheduler/status` (GET)
- **Location:** `/backend/app/main.py:2891-2926`
- **Function:** Get background scheduler status
- **Recommendation:** Add to **scheduling-service** OR **analytics-service**

---

### 6. WEBSOCKET (Completely Missing)

#### `/ws/ticket/{ticket_id}` (WebSocket)
- **Location:** `/backend/app/main.py:3015-3030`
- **Function:** Real-time ticket updates via WebSocket
- **Recommendation:** Add to **ticket-service** OR create separate **websocket-service**

---

## Summary by Priority

### 🔴 CRITICAL (Blocking user - must fix immediately)

1. **Dashboard Metrics** - `/api/v1/dashboard/metrics`
   - Without this, main dashboard is empty
   - User specifically reported this issue

2. **Dashboard Activity** - `/api/v1/dashboard/activity`
   - Shows recent activity feed
   - Part of main dashboard

### 🟠 HIGH (Core functionality missing)

3. **Ticket Processing** - `/api/v1/tickets/process`
4. **Ticket Resolution** - `/api/v1/tickets/{id}/resolve`
5. **Activities/Audit Log** - `/api/v1/activities`
6. **ML Predictions** - Multiple endpoints for ML predictions
7. **Team Performance Analytics** - `/api/v1/analytics/team-performance`

### 🟡 MEDIUM (Nice to have)

8. **WebSocket Support** - Real-time updates
9. **Scheduler Status** - Background job monitoring
10. **ML Model Training** - `/api/v1/ml/train`

---

## Recommended Action Plan

### Phase 1: Fix Dashboard (IMMEDIATE - 2 hours)

**Goal:** Get the dashboard working so user can see data

**Actions:**
1. Add `/api/v1/dashboard/metrics` to analytics-service
2. Add `/api/v1/dashboard/activity` to analytics-service
3. Test dashboard loads with all metrics
4. Deploy and verify with user

**Files to modify:**
- `production-services/analytics-service/main.py`

### Phase 2: Add Missing Ticket Endpoints (4 hours)

**Goal:** Complete ticket functionality

**Actions:**
1. Add `/api/v1/tickets/process` to ticket-service
2. Add `/api/v1/tickets/{id}/resolve` to ticket-service
3. Test ticket operations work end-to-end

**Files to modify:**
- `production-services/ticket-service/main.py`

### Phase 3: Add Analytics & ML Endpoints (6 hours)

**Goal:** Complete analytics and ML predictions

**Actions:**
1. Add all missing ML prediction endpoints to analytics-service
2. Add team performance endpoint
3. Add model status endpoint
4. Test all analytics features

**Files to modify:**
- `production-services/analytics-service/main.py`

### Phase 4: Add Activities/Audit Log (3 hours)

**Goal:** Enable activity tracking

**Actions:**
1. Add activities endpoints to ticket-service OR create activity-service
2. Test activity logging works

### Phase 5: Optional Enhancements (8+ hours)

- WebSocket support for real-time updates
- Scheduler status monitoring
- ML model training endpoint

---

## Quick Fix Option

If time is limited, you can **temporarily use the old monolithic backend** for dashboard data:

1. Keep old backend running on port 8000
2. Update frontend to call old backend for dashboard endpoints
3. Use microservices for everything else
4. Migrate dashboard endpoints to microservices over time

**Update Kong routes:**
```bash
# Route dashboard to old backend
curl -X POST http://localhost:8444/services \
  --data name=legacy-dashboard \
  --data url=http://devops-tickets-backend:8000

curl -X POST http://localhost:8444/services/legacy-dashboard/routes \
  --data paths=/api/v1/dashboard
```

---

## Files to Reference

### Old Backend Files:
- `/backend/app/main.py` - All inline endpoints (2,000+ lines)
- `/backend/app/api/v1/auth.py` - Auth endpoints
- `/backend/app/api/v1/scheduling.py` - Scheduling endpoints
- `/backend/app/api/v1/work_sessions.py` - Work session endpoints
- `/backend/app/api/v1/projects.py` - Project endpoints
- `/backend/app/services/` - Business logic services
- `/backend/app/models/` - Database models

### Microservices Files:
- `production-services/*/main.py` - All 11 microservices

---

## Conclusion

The microservices are missing approximately **20-25 critical endpoints** from the old backend. The most critical issue is the **missing dashboard endpoints** which the user has reported.

**Immediate next step:** Add dashboard metrics endpoint to analytics-service to unblock the user.
