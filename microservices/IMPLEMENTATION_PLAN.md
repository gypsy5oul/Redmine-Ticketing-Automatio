# Complete Implementation Plan - Microservices Feature Parity

## Current Status Summary

### ✅ COMPLETED (Just Now)
1. **Background Scheduler** - All 9 jobs implemented and running
   - Process tickets every 2 min
   - Check SLA every 1 min
   - Update workload every 5 min
   - Daily summary at 9 AM
   - Capacity alerts every 30 min
   - ML retraining Sunday 2 AM
   - Redmine sync every 5 min
   - Ensure shifts daily 6 AM
   - On-call roster Monday 8 AM

2. **Kong API Gateway** - All routes configured
   - Added 8 missing route groups
   - All services now routed correctly

3. **Complete Audit** - FRONTEND_BACKEND_AUDIT.md created
   - All 11 frontend pages analyzed
   - All API calls documented
   - Missing endpoints identified

### 🔴 CRITICAL - Must Implement Now

#### Scheduling Service Endpoints (13 endpoints causing 404s)

**File: `production-services/scheduling-service/main.py`**

Current status: Has `/api/v1/scheduling/*` endpoints but frontend calls `/api/v1/*`

**Required Endpoints:**

1. **Shifts Management**
   ```python
   GET    /api/v1/shifts              # List shifts (with grouping support)
   POST   /api/v1/shifts              # Create shift
   PUT    /api/v1/shifts/{id}         # Update shift
   DELETE /api/v1/shifts/{id}         # Delete shift
   ```

2. **Leave Management**
   ```python
   GET    /api/v1/leaves              # List all leaves (managers only)
   GET    /api/v1/leaves/me           # Get my leaves
   POST   /api/v1/leaves              # Create leave request
   PUT    /api/v1/leaves/{id}         # Update leave
   DELETE /api/v1/leaves/{id}         # Delete leave
   POST   /api/v1/leaves/{id}/status  # Approve/reject leave
   ```

3. **On-Call Management**
   ```python
   GET    /api/v1/oncall/assignments           # Get assignments for week
   POST   /api/v1/oncall/assignments/run       # Generate roster
   GET    /api/v1/oncall/rotate                # Rotate assignment
   POST   /api/v1/oncall/assignments/{id}/replace  # Replace engineer
   ```

**Implementation Approach:**
- Port logic from `/backend/app/api/v1/scheduling.py` (510 lines)
- Port service logic from `/backend/app/services/scheduling_service.py`
- Add database models if not present (ShiftAssignment, MemberLeave, OnCallAssignment)
- Implement authentication/authorization checks
- Handle approval workflows for leaves
- Implement rotation logic for on-call

**Estimated Lines of Code:** ~800-1000 lines

**Estimated Time:** 2-3 hours

---

### ⚠️ MEDIUM Priority - Authentication Issues

#### Team Management Redirect Issue

**Problem:** When clicking Member Performance in Team Management, redirects to login

**Possible Causes:**
1. JWT token not being passed correctly through Kong
2. Token expiration
3. Authorization check failing in team-service
4. CORS issue with credentials

**Investigation Needed:**
1. Check browser DevTools Network tab for failed requests
2. Verify JWT token in Authorization header
3. Check team-service logs for auth failures
4. Test with Postman to isolate frontend vs backend issue

**Files to Check:**
- `frontend/src/contexts/AuthContext.tsx` - Token storage/retrieval
- `frontend/src/services/api.ts` - Authorization header setting
- `team-service/main.py` - Auth middleware
- Kong config - JWT plugin configuration

---

### 🟡 LOW Priority - Nice to Have

#### Project Service Implementation

**Status:** Service doesn't exist yet

**Required Endpoints:**
```python
GET /api/v1/projects/summaries      # List all projects
GET /api/v1/projects/{jiraId}       # Get project details
```

**Note:** Only needed if Projects page is actively used. Check with user.

**Implementation:**
- Create new `project-service` directory
- Port from old backend project logic
- Add to docker-compose
- Already has Kong route configured

---

#### Activities Endpoint

**Required:**
```python
GET /api/v1/activities  # For Dashboard recent activity widget
```

**Options:**
1. Add to ticket-service (activities are ticket-related)
2. Add to analytics-service (part of dashboard)

**Recommendation:** Add to ticket-service since activities are primarily ticket events

---

## Recommended Implementation Order

### Phase 1: Critical Path (Now)
1. ✅ Fix Kong routes - **DONE**
2. ⬜ Implement scheduling endpoints - **IN PROGRESS**
   - Start with shifts (4 endpoints)
   - Then leaves (6 endpoints)
   - Then on-call (3 endpoints)

### Phase 2: Fix Auth Issues (After Phase 1)
3. ⬜ Debug team management redirect
4. ⬜ Test all authenticated endpoints

### Phase 3: Optional Features (If Needed)
5. ⬜ Implement project service (if Projects page used)
6. ⬜ Add activities endpoint (for Dashboard widget)

---

## Testing Plan

After implementation:

1. **Smoke Test Each Page:**
   ```bash
   # Check for 404 errors in browser DevTools
   - Dashboard ✓
   - Scheduling (13 endpoints)
   - Team Management
   - Member Performance
   - Ticket Monitoring
   - Collaboration Workspace
   - Analytics
   - Projects (if implemented)
   - SLA Configuration
   ```

2. **Test Background Scheduler:**
   ```bash
   # Watch logs for job execution
   docker logs scheduling-service -f

   # Check scheduler status
   curl http://localhost:8000/api/v1/scheduler/status

   # Check job logs
   curl http://localhost:8000/api/v1/scheduler/logs
   ```

3. **Test Authentication:**
   - Login as different user roles
   - Verify access control works
   - Check no unexpected redirects

---

## Code Examples

### Shifts Endpoint (Reference)

From old backend `/backend/app/api/v1/scheduling.py:147-201`:

```python
@router.get("/shifts")
async def list_shifts(
    team_level: Optional[str] = Query(default=None),
    member_id: Optional[int] = Query(default=None),
    include_inactive: bool = Query(default=False),
    grouped: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    service = SchedulingService(db)
    shifts = service.list_shift_assignments(
        team_level=team_level,
        member_id=member_id,
        include_inactive=include_inactive,
    )

    if grouped:
        # Group by team member
        grouped_data = {}
        for shift in shifts:
            member_id = shift.team_member_id
            if member_id not in grouped_data:
                grouped_data[member_id] = {
                    "team_member_id": member_id,
                    "team_member_name": shift.team_member.name,
                    "team_level": shift.team_level,
                    "shifts": []
                }
            grouped_data[member_id]["shifts"].append(serialize_shift(shift))

        return {"count": len(grouped_data), "grouped_shifts": list(grouped_data.values())}

    return {"count": len(shifts), "shifts": [serialize_shift(s) for s in shifts]}
```

This needs to be adapted for microservices (no SchedulingService class, direct DB access).

---

## Next Steps

**Immediate Action Required:**

1. Implement scheduling endpoints in `scheduling-service/main.py`
2. Test Scheduling page - verify no 404 errors
3. Push changes to GitHub
4. Test background scheduler is running
5. Debug auth issue if time permits

**Decision Needed from User:**

1. Do you actively use the Projects page? (If no, we can skip project-service)
2. Do you need the Dashboard recent activity widget? (If no, skip activities endpoint)
3. Should I focus on getting Scheduling page working first, then tackle auth issues?

---

## Files Modified So Far

1. ✅ `microservices/api-gateway/kong-config.yml` - Added 8 route groups
2. ✅ `microservices/production-services/scheduling-service/main.py` - Added background scheduler
3. ✅ `microservices/production-services/scheduling-service/requirements.txt` - Added apscheduler
4. ✅ `microservices/FRONTEND_BACKEND_AUDIT.md` - Created audit report
5. ✅ `microservices/IMPLEMENTATION_PLAN.md` - This file

**Next File to Modify:**
- `microservices/production-services/scheduling-service/main.py` - Add ~800 lines for endpoints

---

## Estimated Total Remaining Work

- **Scheduling endpoints:** 2-3 hours (800-1000 LOC)
- **Auth debugging:** 30-60 minutes
- **Project service:** 1-2 hours (if needed)
- **Activities endpoint:** 30 minutes (if needed)
- **Testing:** 1 hour

**Total:** 4-7 hours depending on scope

---

## Summary

**What's Working:**
- Background scheduler (all 9 jobs)
- Kong routing (all configured)
- Most services (auth, team, ticket, SLA, workload, analytics, escalation, integration)

**What's Broken:**
- Scheduling page (13 endpoint 404s) - **CRITICAL**
- Team management redirect - **MEDIUM**
- Projects page - **LOW** (if used)
- Dashboard activity widget - **LOW** (if needed)

**Priority:** Fix Scheduling page first (biggest user impact), then auth issues.
