# Authentication Implementation Guide

**Date:** November 6, 2025
**Status:** IN PROGRESS
**Priority:** CRITICAL

---

## Quick Reference

### Step 1: Add Dependencies to requirements.txt
```txt
python-jose[cryptography]==3.3.0
```

### Step 2: Add Imports to main.py
```python
import sys
import os
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.auth_utils import (
    setup_logging,
    log_request,
    log_error,
    get_current_user,
    require_admin,
    require_manager,
    User
)

# Replace existing logger setup
logger = setup_logging("your-service-name", "INFO")
```

### Step 3: Add Auth to Endpoints

**Pattern for public endpoints (anyone can call):**
```python
# No changes needed - keep as is
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**Pattern for authenticated endpoints (any logged-in user):**
```python
@app.get("/api/v1/resource")
async def get_resource(
    user: User = Depends(get_current_user),  # ← ADD THIS
    request: Request = None,                  # ← ADD THIS
    db: Session = Depends(get_db)
):
    log_request(logger, request, user.id, "GET /api/v1/resource")  # ← ADD THIS
    # existing code...
```

**Pattern for admin-only endpoints:**
```python
@app.post("/api/v1/admin/resource")
async def create_resource(
    user: User = Depends(require_admin),  # ← ADD THIS (admin only)
    request: Request = None,
    payload: dict,
    db: Session = Depends(get_db)
):
    log_request(logger, request, user.id, "POST /api/v1/admin/resource")
    # existing code...
```

**Pattern for manager-level endpoints:**
```python
@app.get("/api/v1/team/members")
async def get_team_members(
    user: User = Depends(require_manager),  # ← Requires manager/admin/super_admin
    request: Request = None,
    db: Session = Depends(get_db)
):
    log_request(logger, request, user.id, "GET /api/v1/team/members")
    # existing code...
```

---

## Service-by-Service Implementation

### 1. ✅ auth-service (Port 8101)
**Status:** Special case - login endpoint must stay open
**Action:**
- Keep `/api/v1/auth/login` open (no auth)
- Add auth to `/api/v1/auth/me` endpoint
- Add auth to `/api/v1/auth/refresh`

---

### 2. ⚠️ scheduling-service (Port 8010) - CRITICAL
**Status:** IN PROGRESS
**Endpoints:** 13 (shifts, leaves, on-call)

**Auth Requirements:**
| Endpoint | Method | Auth Level | Reason |
|----------|--------|------------|--------|
| GET /api/v1/shifts | GET | `require_manager` | Only managers view all shifts |
| POST /api/v1/shifts | POST | `require_admin` | Only admins create shifts |
| PUT /api/v1/shifts/{id} | PUT | `require_admin` | Only admins modify shifts |
| DELETE /api/v1/shifts/{id} | DELETE | `require_admin` | Only admins delete shifts |
| GET /api/v1/leaves | GET | `require_manager` | Only managers view all leaves |
| GET /api/v1/leaves/me | GET | `get_current_user` | Users can view their own leaves |
| POST /api/v1/leaves | POST | `get_current_user` | Any user can request leave |
| PUT /api/v1/leaves/{id} | PUT | `get_current_user` + check ownership | Users edit own, managers edit all |
| DELETE /api/v1/leaves/{id} | DELETE | `require_manager` | Only managers delete leaves |
| POST /api/v1/leaves/{id}/status | POST | `require_manager` | Only managers approve/reject |
| GET /api/v1/oncall/assignments | GET | `get_current_user` | Any user can view roster |
| POST /api/v1/oncall/assignments/run | POST | `require_manager` | Only managers generate roster |
| GET /api/v1/oncall/rotate | GET | `require_manager` | Only managers rotate |
| POST /api/v1/oncall/assignments/{id}/replace | POST | `require_admin` | Only admins replace assignments |

---

### 3. ⚠️ project-service (Port 8011) - CRITICAL
**Status:** IN PROGRESS
**Endpoints:** 2

**Auth Requirements:**
| Endpoint | Auth Level |
|----------|------------|
| GET /api/v1/projects | `get_current_user` |
| GET /api/v1/projects/{id} | `get_current_user` |

---

### 4. ⚠️ ticket-service (Port 8102) - HIGH PRIORITY
**Status:** PENDING
**Endpoints:** ~20

**Auth Requirements:**
- All ticket endpoints: `get_current_user`
- Work session endpoints: `get_current_user`
- Collaboration endpoints: `get_current_user`
- Comment endpoints: `get_current_user`

---

### 5. ⚠️ team-service (Port 8103) - HIGH PRIORITY
**Status:** PENDING
**Endpoints:** ~8

**Auth Requirements:**
- GET /api/v1/team/members: `get_current_user`
- POST /api/v1/team/members: `require_admin`
- PUT /api/v1/team/members/{id}: `require_admin`
- DELETE /api/v1/team/members/{id}: `require_admin`
- GET /api/v1/team/members/{id}/performance: `get_current_user`

---

### 6. sla-service (Port 8104)
**Auth:** All endpoints require `get_current_user`
Admin operations (create/update policies): `require_admin`

### 7. workload-service (Port 8105)
**Auth:** All endpoints require `get_current_user`

### 8. analytics-service (Port 8106)
**Auth:** All endpoints require `get_current_user`

### 9. escalation-service (Port 8107)
**Auth:** All endpoints require `get_current_user`
Manual escalation: `require_manager`

### 10. integration-service (Port 8108)
**Auth:** All endpoints require `get_current_user`
Redmine sync: `require_admin`

---

## Error Handling Patterns

### Log Errors with Context
```python
try:
    # operation
    result = do_something()
    return {"success": True, "data": result}
except Exception as e:
    log_error(logger, request, user.id, e, "Failed to do something")
    raise HTTPException(status_code=500, detail=str(e))
```

### Check Resource Ownership
```python
from shared.auth_utils import can_manage_resource

@app.put("/api/v1/leaves/{leave_id}")
async def update_leave(
    leave_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    payload: dict,
    db: Session = Depends(get_db)
):
    log_request(logger, request, user.id, f"PUT /api/v1/leaves/{leave_id}")

    leave = db.query(MemberLeave).filter(MemberLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(404, "Leave not found")

    # Check if user owns the resource or is admin
    if not can_manage_resource(user, leave.team_member_id):
        raise HTTPException(403, "Not authorized to modify this leave")

    # Update leave...
```

---

## Dockerfile Updates

Each service's Dockerfile needs to copy the shared module:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared utilities
COPY ../../shared /app/shared

# Copy application
COPY main.py .

# Expose port
EXPOSE 8010

# Run service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010"]
```

---

## Testing Authentication

### Test with Valid Token
```bash
# Get token
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' | jq -r '.access_token')

# Use token
curl http://localhost:8000/api/v1/shifts \
  -H "Authorization: Bearer $TOKEN"

# Should return: 200 OK with data
```

### Test without Token
```bash
curl http://localhost:8000/api/v1/shifts

# Should return: 401 Unauthorized
```

### Test with Wrong Role
```bash
# Login as L1 user
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"engineer","password":"engineer"}' | jq -r '.access_token')

# Try to approve leave (requires manager)
curl -X POST http://localhost:8000/api/v1/leaves/1/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved"}'

# Should return: 403 Forbidden
```

---

## Progress Tracking

| Service | Requirements Added | Imports Added | Auth Applied | Tested | Status |
|---------|-------------------|---------------|--------------|--------|--------|
| auth-service | ✅ | ⬜ | ⬜ | ⬜ | PENDING |
| scheduling-service | ⬜ | ⬜ | ⬜ | ⬜ | IN PROGRESS |
| project-service | ⬜ | ⬜ | ⬜ | ⬜ | IN PROGRESS |
| ticket-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| team-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| sla-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| workload-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| analytics-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| escalation-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |
| integration-service | ⬜ | ⬜ | ⬜ | ⬜ | PENDING |

---

## Environment Variables

Add to `.env` or `docker-compose.yml`:

```env
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production-minimum-32-characters-required
JWT_ALGORITHM=HS256
LOG_LEVEL=INFO
```

---

## Timeline Estimate

| Task | Time | Status |
|------|------|--------|
| Shared module created | 30 min | ✅ DONE |
| scheduling-service | 30 min | 🔄 IN PROGRESS |
| project-service | 15 min | 🔄 IN PROGRESS |
| ticket-service | 45 min | ⬜ PENDING |
| team-service | 30 min | ⬜ PENDING |
| Other services (6) | 2 hours | ⬜ PENDING |
| Testing | 1 hour | ⬜ PENDING |
| **TOTAL** | **5 hours** | 10% COMPLETE |

---

## Next Steps

1. ✅ Create shared auth module
2. 🔄 Add auth to scheduling-service
3. 🔄 Add auth to project-service
4. ⬜ Add auth to ticket-service
5. ⬜ Add auth to team-service
6. ⬜ Add auth to remaining services
7. ⬜ Update all Dockerfiles
8. ⬜ Test all endpoints
9. ⬜ Update docker-compose with JWT env vars

---

**Current Status:** Shared module complete, applying to critical services now.
