# Implementation Strategy - All Missing Endpoints

## Overview
Implementing all 20 missing endpoints across 4 phases with incremental commits.

## Phase 1: Analytics Service (11 endpoints) - CRITICAL

### 1A: Dashboard Endpoints (HIGH PRIORITY)
**File:** `production-services/analytics-service/main.py`

#### Endpoint 1: GET /api/v1/dashboard/metrics
- **Source:** `/backend/app/main.py:1954-2228` (274 lines)
- **Complexity:** HIGH - Complex SQL queries, 7-day sparklines, distributions
- **Dependencies:** TicketHistory, SLATracker, TeamMember, TicketCollaboration models
- **Returns:** 8 key metrics + card_insights with sparklines/distributions

#### Endpoint 2: GET /api/v1/dashboard/activity
- **Source:** `/backend/app/main.py:2231-2262` (31 lines)
- **Complexity:** MEDIUM - Recent activity query
- **Dependencies:** Activity model
- **Returns:** List of recent activities with ticket info

### 1B: ML Prediction Endpoints

#### Endpoint 3: POST /api/v1/ml/predict/category
- **Source:** `/backend/app/main.py:1819-1844`
- **Status:** Exists as `/api/v1/ml/predict-category` - needs path update

#### Endpoint 4: POST /api/v1/ml/predict/complexity
- **Source:** `/backend/app/main.py:1846-1873`
- **Complexity:** MEDIUM - Uses ML service

#### Endpoint 5: POST /api/v1/ml/predict/resolution-time
- **Source:** `/backend/app/main.py:1875-1901`
- **Complexity:** MEDIUM - Uses ML service

#### Endpoint 6: POST /api/v1/ml/predict/all
- **Source:** `/backend/app/main.py:1903-1952`
- **Complexity:** HIGH - Calls all prediction endpoints

### 1C: Analytics Endpoints

#### Endpoint 7: GET /api/v1/analytics/forecast
- **Source:** `/backend/app/main.py:1665-1674`
- **Status:** EXISTS - verify compatibility

#### Endpoint 8: GET /api/v1/analytics/sla-prediction/{ticket_id}
- **Source:** `/backend/app/main.py:1676-1693`
- **Complexity:** MEDIUM - SLA breach prediction

#### Endpoint 9: POST /api/v1/ml/train
- **Source:** `/backend/app/main.py:1695-1714`
- **Complexity:** HIGH - Triggers ML model training

#### Endpoint 10: GET /api/v1/analytics/team-performance
- **Source:** `/backend/app/main.py:1716-1781` (65 lines)
- **Status:** EXISTS as `/api/v1/analytics/performance` - needs enhancement
- **Complexity:** HIGH - Detailed team performance with workload metrics

#### Endpoint 11: GET /api/v1/ml/models/status
- **Source:** `/backend/app/main.py:1783-1817`
- **Complexity:** MEDIUM - ML model status and accuracy

---

## Phase 2: Ticket Service (4 endpoints)

### File: `production-services/ticket-service/main.py`

#### Endpoint 12: POST /api/v1/tickets
- **Source:** Needs to be created (currently missing)
- **Function:** Create new ticket
- **Complexity:** MEDIUM

#### Endpoint 13: POST /api/v1/tickets/process
- **Source:** `/backend/app/main.py:730-749`
- **Function:** Batch process tickets
- **Complexity:** MEDIUM - Triggers TicketProcessor service

#### Endpoint 14: POST /process-tickets (Legacy)
- **Source:** `/backend/app/main.py:751-767`
- **Function:** Legacy endpoint for backwards compatibility
- **Complexity:** LOW - Redirects to new endpoint

#### Endpoint 15: POST /api/v1/tickets/{ticket_id}/resolve
- **Source:** `/backend/app/main.py:769-881` (112 lines)
- **Function:** Resolve ticket with resolution notes
- **Complexity:** HIGH - Updates ticket, posts to Redmine, creates activity

---

## Phase 3: Activities Service (2 endpoints)

### File: `production-services/ticket-service/main.py` (add to existing)

#### Endpoint 16: GET /api/v1/activities
- **Source:** `/backend/app/main.py:2928-2959`
- **Function:** Get all system activities
- **Complexity:** MEDIUM

#### Endpoint 17: GET /api/v1/activities/ticket/{ticket_id}
- **Source:** `/backend/app/main.py:2961-2994`
- **Function:** Get activities for specific ticket
- **Complexity:** MEDIUM

---

## Phase 4: Remaining Endpoints (3 endpoints)

### Endpoint 18: GET /api/v1/team/members/{member_id}/performance
- **File:** `production-services/team-service/main.py`
- **Source:** `/backend/app/main.py:2748-2889` (141 lines)
- **Function:** Detailed member performance metrics
- **Complexity:** HIGH - Comprehensive performance analysis

### Endpoint 19: POST /api/v1/redmine/sync-statuses
- **File:** `production-services/integration-service/main.py`
- **Source:** `/backend/app/main.py:2378-2396`
- **Function:** Sync ticket statuses with Redmine
- **Complexity:** MEDIUM

### Endpoint 20: GET /api/v1/scheduler/status
- **File:** `production-services/scheduling-service/main.py`
- **Source:** `/backend/app/main.py:2891-2926`
- **Function:** Get background scheduler status
- **Complexity:** MEDIUM

---

## Models Needed

Ensure these models exist in each service:

### Analytics Service Needs:
- TicketHistory (exists)
- TeamMember (exists)
- SLATracker (add)
- SLAStatus enum (add)
- TicketStatus enum (add)
- TicketPriority enum (add)
- TicketCollaboration (add)
- Activity (add)

### Ticket Service Needs:
- TicketHistory
- TicketComment
- Activity (add)
- SLATracker (for resolve endpoint)

---

## Implementation Order

### Day 1 (4-6 hours): Phase 1A - Critical Dashboard
1. Add all required models to analytics-service
2. Implement /api/v1/dashboard/metrics
3. Implement /api/v1/dashboard/activity
4. Test dashboard loads
5. **COMMIT & PUSH**

### Day 1 (2-3 hours): Phase 1B - ML Predictions
6. Implement /api/v1/ml/predict/complexity
7. Implement /api/v1/ml/predict/resolution-time
8. Implement /api/v1/ml/predict/all
9. Update existing predict-category path
10. **COMMIT & PUSH**

### Day 2 (2-3 hours): Phase 1C - Analytics
11. Implement /api/v1/analytics/sla-prediction/{id}
12. Implement /api/v1/ml/train
13. Enhance /api/v1/analytics/team-performance
14. Implement /api/v1/ml/models/status
15. **COMMIT & PUSH**

### Day 2 (2-3 hours): Phase 2 - Tickets
16. Add Activity model to ticket-service
17. Implement POST /api/v1/tickets (create)
18. Implement POST /api/v1/tickets/process
19. Implement POST /api/v1/tickets/{id}/resolve
20. Implement POST /process-tickets (legacy)
21. **COMMIT & PUSH**

### Day 3 (2 hours): Phase 3 - Activities
22. Implement GET /api/v1/activities
23. Implement GET /api/v1/activities/ticket/{id}
24. **COMMIT & PUSH**

### Day 3 (2 hours): Phase 4 - Remaining
25. Implement GET /api/v1/team/members/{id}/performance
26. Implement POST /api/v1/redmine/sync-statuses
27. Implement GET /api/v1/scheduler/status
28. **COMMIT & PUSH**

### Final (1 hour): Testing
29. Rebuild all services
30. Update Kong routes
31. Test all endpoints
32. Verify frontend works end-to-end
33. **FINAL COMMIT & PUSH**

---

## Testing Strategy

After each commit:
1. Rebuild affected service(s)
2. Restart service(s)
3. Test new endpoints via curl/Postman
4. Check service logs for errors
5. Verify no regressions

Final testing:
1. Start all services
2. Configure Kong routes
3. Test frontend navigation
4. Verify dashboard loads
5. Test ticket operations
6. Verify all pages show data

---

## Risk Mitigation

- **Frequent commits:** After each phase completion
- **Incremental testing:** Test each endpoint as added
- **Model compatibility:** Verify all models match database schema
- **Service dependencies:** Handle missing services gracefully
- **Error handling:** Comprehensive try-catch blocks

---

## Estimated Timeline

- **Phase 1:** 8-9 hours
- **Phase 2:** 2-3 hours
- **Phase 3:** 2 hours
- **Phase 4:** 2 hours
- **Testing:** 1 hour

**TOTAL: 15-17 hours**

With focused work: Can complete in 2-3 days
