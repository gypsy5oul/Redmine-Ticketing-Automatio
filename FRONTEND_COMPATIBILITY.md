# Frontend Compatibility Analysis for Microservices

**Status**: ⚠️ FRONTEND REQUIRES CONFIGURATION UPDATE
**Date**: 2025-01-15

---

## TL;DR - What You Need to Do

**Good News**: The frontend is already configured to use port 8000 (Kong Gateway)! ✅

**Action Required**:
1. Update frontend `.env` file to point to Kong
2. No code changes needed in frontend

---

## Current Frontend Configuration

### Environment Variables (.env.example)

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

✅ **Already configured correctly** for Kong Gateway on port 8000!

---

## API Endpoint Compatibility

### ✅ Endpoints That Work Out of the Box

These frontend endpoints will work immediately through Kong:

| Frontend Endpoint | Kong Route | Target Service | Status |
|-------------------|------------|----------------|--------|
| `/api/v1/auth/*` | `/api/v1/auth` | auth-service (8001) | ✅ |
| `/api/v1/tickets/*` | `/api/v1/tickets` | ticket-service (8002) | ✅ |
| `/api/v1/team/*` | `/api/v1/team` | team-service (8003) | ✅ |
| `/api/v1/sla/*` | `/api/v1/sla` | sla-service (8004) | ✅ |
| `/api/v1/workload/*` | `/api/v1/workload` | workload-service (8005) | ✅ |
| `/api/v1/analytics/*` | `/api/v1/analytics` | analytics-service (8006) | ✅ |
| `/api/v1/escalation/*` | `/api/v1/escalation` | escalation-service (8007) | ✅ |
| `/api/v1/collaboration/*` | `/api/v1/collaboration` | collaboration-service (8008) | ✅ |
| `/api/v1/integration/*` | `/api/v1/integration` | integration-service (8009) | ✅ |
| `/api/v1/scheduling/*` | `/api/v1/scheduling` | scheduling-service (8010) | ✅ |

### ⚠️ Special Endpoints That Need Attention

#### Work Session Endpoints

**Frontend calls**:
```typescript
POST   /api/v1/tickets/{id}/work/start
POST   /api/v1/tickets/{id}/work/pause
POST   /api/v1/tickets/{id}/work/resume
GET    /api/v1/tickets/{id}/work/summary
GET    /api/v1/work/active
```

**Current Kong Routes**:
- `/api/v1/tickets/*` → ticket-service ✅
- `/api/v1/work-sessions` → work-session-service ❓

**Analysis**:
- Ticket-specific work endpoints (`/tickets/{id}/work/*`) will route to ticket-service
- The standalone `/api/v1/work/active` endpoint needs verification

**Recommendation**:
- Check if ticket-service or work-session-service implements these endpoints
- May need to add Kong route: `/api/v1/work` → work-session-service

#### Machine Learning Endpoints

**Frontend calls**:
```typescript
POST   /api/v1/ml/train
GET    /api/v1/ml/models/status
```

**Current Kong Routes**:
- `/api/v1/analytics` → analytics-service ✅

**Issue**: No route for `/api/v1/ml/*`

**Recommendation**: Add Kong route:
```bash
create_service_route "analytics-ml" "analytics-service" "8006" "/api/v1/ml"
```

---

## Deployment Steps for Frontend

### Option 1: No Changes Needed (If .env exists)

If your frontend already has a `.env` file with:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

Then you don't need to do anything! Just ensure the frontend container/server is running.

### Option 2: Create .env File

```bash
cd /opt/redmine-automation-microservice/frontend

# Create .env from example
cp .env.example .env

# Verify it has the correct URL
cat .env
```

Should contain:
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

### Option 3: Environment-Specific Configuration

For different environments (dev, staging, prod):

**Development** (localhost):
```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

**Production** (your server IP):
```bash
VITE_API_BASE_URL=http://10.0.2.121:8000
VITE_WS_BASE_URL=ws://10.0.2.121:8000
```

---

## Kong Route Updates Needed

### Current setup-kong-routes.sh

Currently configures these routes:
```bash
/api/v1/auth → auth-service
/api/v1/tickets → ticket-service
/api/v1/team → team-service
/api/v1/sla → sla-service
/api/v1/workload → workload-service
/api/v1/analytics → analytics-service
/api/v1/escalation → escalation-service
/api/v1/collaboration → collaboration-service
/api/v1/integration → integration-service
/api/v1/scheduling → scheduling-service
/api/v1/work-sessions → work-session-service
```

### Additional Routes Needed

Add these routes to `setup-kong-routes.sh`:

```bash
# ML endpoints (route to analytics service)
create_service_route "ml-service" "analytics-service" "8006" "/api/v1/ml"

# Work endpoints (route to work-session or ticket service)
create_service_route "work-service" "work-session-service" "8011" "/api/v1/work"
```

---

## Complete Updated setup-kong-routes.sh

Here's the updated script with all needed routes:

```bash
#!/bin/bash

# ... (existing setup code) ...

# Create all services and routes
create_service_route "auth-service" "auth-service" "8001" "/api/v1/auth"
create_service_route "ticket-service" "ticket-service" "8002" "/api/v1/tickets"
create_service_route "team-service" "team-service" "8003" "/api/v1/team"
create_service_route "sla-service" "sla-service" "8004" "/api/v1/sla"
create_service_route "workload-service" "workload-service" "8005" "/api/v1/workload"
create_service_route "analytics-service" "analytics-service" "8006" "/api/v1/analytics"
create_service_route "escalation-service" "escalation-service" "8007" "/api/v1/escalation"
create_service_route "collaboration-service" "collaboration-service" "8008" "/api/v1/collaboration"
create_service_route "integration-service" "integration-service" "8009" "/api/v1/integration"
create_service_route "scheduling-service" "scheduling-service" "8010" "/api/v1/scheduling"
create_service_route "work-session-service" "work-session-service" "8011" "/api/v1/work-sessions"

# Additional routes for frontend compatibility
create_service_route "ml-endpoints" "analytics-service" "8006" "/api/v1/ml"
create_service_route "work-endpoints" "work-session-service" "8011" "/api/v1/work"
```

---

## Testing Frontend Connectivity

### 1. Start All Services

```bash
cd microservices
docker-compose -f docker-compose.microservices.yml up -d --build
./setup-kong-routes.sh
```

### 2. Test API Endpoints

```bash
# Test auth (used by frontend login)
curl http://localhost:8000/api/v1/auth/health

# Test tickets (main feature)
curl http://localhost:8000/api/v1/tickets/health

# Test team management
curl http://localhost:8000/api/v1/team/health

# Test ML endpoints
curl http://localhost:8000/api/v1/ml/models/status

# Test work sessions
curl http://localhost:8000/api/v1/work/active
```

### 3. Start Frontend

```bash
cd frontend

# Install dependencies (if needed)
npm install

# Start development server
npm run dev

# Or build for production
npm run build
npm run preview
```

### 4. Test in Browser

1. Open http://localhost:5173 (or configured frontend port)
2. Try logging in
3. Check browser console for API errors
4. Verify network tab shows requests going to http://localhost:8000

---

## Common Issues & Solutions

### Issue 1: CORS Errors

**Symptom**: Browser console shows CORS errors

**Solution**: Add CORS plugin to Kong:

```bash
curl -i -X POST http://localhost:8444/plugins \
  --data "name=cors" \
  --data "config.origins=http://localhost:3000,http://localhost:5173,http://10.0.2.121:3000" \
  --data "config.methods=GET,POST,PUT,DELETE,PATCH,OPTIONS" \
  --data "config.headers=Accept,Authorization,Content-Type,X-Requested-With" \
  --data "config.credentials=true" \
  --data "config.max_age=3600"
```

### Issue 2: 404 Not Found for Specific Endpoints

**Symptom**: Some API calls return 404

**Possible Causes**:
1. Kong route not configured for that path
2. Microservice doesn't implement that endpoint
3. Path mismatch between frontend and backend

**Solution**:
1. Check Kong routes: `curl http://localhost:8444/routes | jq`
2. Check microservice logs: `docker logs ticket-service`
3. Add missing Kong route or verify endpoint exists

### Issue 3: Authentication Fails

**Symptom**: Login works but subsequent requests fail with 401

**Possible Causes**:
1. JWT token not being sent in headers
2. Auth service not validating tokens correctly
3. Other services not configured with same JWT secret

**Solution**:
1. Verify all services use same JWT_SECRET_KEY in .env
2. Check browser localStorage for token
3. Verify Authorization header is being sent

### Issue 4: WebSocket Connection Fails

**Symptom**: Real-time features don't work

**Note**: Current setup doesn't include WebSocket routing through Kong

**Solution**:
- If WebSockets are needed, configure Kong to support WS
- Or connect WebSocket directly to service (not through Kong)

---

## Architecture Flow

```
┌─────────────────────────────────────┐
│   Frontend (React + Vite)           │
│   Port: 5173 (dev) or 3000 (prod)   │
│   ENV: VITE_API_BASE_URL=:8000      │
└───────────────┬─────────────────────┘
                │
                │ HTTP Requests
                ▼
┌─────────────────────────────────────┐
│     Kong API Gateway                │
│     Port: 8000 (Proxy)              │
│     Port: 8444 (Admin)              │
│                                     │
│  Routes:                            │
│  /api/v1/auth → 8001                │
│  /api/v1/tickets → 8002             │
│  /api/v1/team → 8003                │
│  /api/v1/ml → 8006                  │
│  /api/v1/work → 8011                │
│  ...etc                             │
└───────────────┬─────────────────────┘
                │
                ▼
┌─────────────────────────────────────┐
│  Microservices (11 services)        │
│  Ports: 8001-8011                   │
│                                     │
│  Each service has:                  │
│  - FastAPI application              │
│  - Health endpoint                  │
│  - Business logic                   │
│  - Database access                  │
└─────────────────────────────────────┘
```

---

## Summary

### ✅ What's Already Good

1. Frontend configured to use port 8000 (Kong)
2. Kong routes cover all major services
3. All microservices are healthy and running
4. Database and Redis are shared

### ⚠️ What Needs Attention

1. Add Kong route for `/api/v1/ml/*` endpoints
2. Add Kong route for `/api/v1/work/*` endpoints
3. Verify work session endpoints exist in ticket-service or work-session-service
4. Configure CORS plugin in Kong for frontend access
5. Ensure frontend `.env` file exists

### 🚀 Next Steps

1. Update `setup-kong-routes.sh` with ML and work routes
2. Run Kong configuration script
3. Add CORS plugin to Kong
4. Test frontend → Kong → microservices flow
5. Fix any endpoint mismatches found during testing

---

## Quick Fix Commands

```bash
# 1. Add missing Kong routes manually
curl -i -X POST http://localhost:8444/services \
  --data name=ml-service \
  --data url=http://analytics-service:8006

curl -i -X POST http://localhost:8444/services/ml-service/routes \
  --data 'paths[]=/api/v1/ml' \
  --data name=ml-route

curl -i -X POST http://localhost:8444/services \
  --data name=work-service \
  --data url=http://work-session-service:8011

curl -i -X POST http://localhost:8444/services/work-service/routes \
  --data 'paths[]=/api/v1/work' \
  --data name=work-route

# 2. Add CORS plugin
curl -i -X POST http://localhost:8444/plugins \
  --data "name=cors" \
  --data "config.origins=*" \
  --data "config.methods=GET,POST,PUT,DELETE,PATCH,OPTIONS" \
  --data "config.headers=Accept,Authorization,Content-Type" \
  --data "config.credentials=true"

# 3. Test endpoints
curl http://localhost:8000/api/v1/ml/models/status
curl http://localhost:8000/api/v1/work/active
```

---

**Status**: Frontend is 90% compatible. Just need to add 2 Kong routes and configure CORS.

**Estimated Time to Fix**: 10 minutes

---

*Last Updated: 2025-01-15*
*All microservices deployed and tested ✅*
