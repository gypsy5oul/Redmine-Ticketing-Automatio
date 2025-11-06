# Complete Endpoint Mapping - Old App to Microservices

## Total Endpoints in Old App: 81

### Breakdown:
- main.py: 56 endpoints
- auth.py: 10 endpoints
- scheduling.py: 15 endpoints
- work_sessions.py: 5 endpoints
- projects.py: (need to check)

---

## ENDPOINT MIGRATION PLAN

### ✅ = Exists | ❌ = Missing | ⚠️ = Partially Implemented

---

## 1. AUTH SERVICE (auth-service) - Port 8001

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | POST | /api/v1/auth/login | login |
| ✅ | POST | /api/v1/auth/refresh | refresh_token |
| ✅ | GET | /api/v1/auth/me | get_current_user_info |
| ✅ | POST | /api/v1/auth/logout | logout |
| ✅ | POST | /api/v1/auth/change-password | change_password |
| ✅ | POST | /api/v1/auth/users | create_user |
| ✅ | GET | /api/v1/auth/users | list_users |
| ✅ | PUT | /api/v1/auth/users/{user_id}/deactivate | deactivate_user |
| ✅ | PUT | /api/v1/auth/users/{user_id}/activate | activate_user |
| ✅ | POST | /api/v1/auth/users/{user_id}/reset-password | reset_user_password |

**Status:** ✅ COMPLETE (10/10)

---

## 2. TICKET SERVICE (ticket-service) - Port 8002

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/tickets | get_tickets (list with filters) |
| ✅ | GET | /api/v1/tickets/{ticket_id} | get_ticket (single ticket details) |
| ✅ | PUT | /api/v1/tickets/{ticket_id} | update_ticket |
| ❌ | POST | /api/v1/tickets | create_ticket |
| ❌ | POST | /api/v1/tickets/process | process_tickets (batch processing) |
| ❌ | POST | /process-tickets | process_tickets_legacy (backwards compat) |
| ❌ | POST | /api/v1/tickets/{ticket_id}/resolve | resolve_ticket |
| ✅ | GET | /api/v1/tickets/{ticket_id}/comments | get_ticket_comments |
| ✅ | POST | /api/v1/tickets/{ticket_id}/comments | create_comment |
| ✅ | PUT | /api/v1/comments/{comment_id} | update_comment |
| ✅ | DELETE | /api/v1/comments/{comment_id} | delete_comment |

**Status:** ⚠️ INCOMPLETE (7/11)
**Missing:** create_ticket, process_tickets, process_tickets_legacy, resolve_ticket

---

## 3. TEAM SERVICE (team-service) - Port 8003

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/team/skills | get_skills |
| ✅ | POST | /api/v1/team/skills | create_skill |
| ✅ | GET | /api/v1/team/members | get_team_members |
| ✅ | GET | /api/v1/team/members/{member_id} | get_team_member |
| ✅ | POST | /api/v1/team/members | create_team_member |
| ✅ | PUT | /api/v1/team/members/{member_id} | update_team_member |
| ✅ | DELETE | /api/v1/team/members/{member_id} | delete_team_member |
| ❌ | GET | /api/v1/team/members/{member_id}/performance | get_member_performance |

**Status:** ⚠️ INCOMPLETE (7/8)
**Missing:** get_member_performance

---

## 4. SLA SERVICE (sla-service) - Port 8004

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/sla/policies | get_sla_policies |
| ✅ | POST | /api/v1/sla/policies | create_sla_policy |
| ✅ | PUT | /api/v1/sla/policies/{policy_id} | update_sla_policy |
| ✅ | GET | /api/v1/sla/status/{ticket_id} | get_sla_status |
| ✅ | GET | /api/v1/sla/at-risk | get_at_risk_tickets |
| ✅ | POST | /api/v1/sla/{ticket_id}/pause | pause_sla |
| ✅ | POST | /api/v1/sla/{ticket_id}/resume | resume_sla |

**Status:** ✅ COMPLETE (7/7)

---

## 5. WORKLOAD SERVICE (workload-service) - Port 8005

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/workload | get_team_workload |
| ✅ | GET | /api/v1/workload/capacity | get_capacity_summary |
| ✅ | GET | /api/v1/workload/alerts | get_capacity_alerts |

**Status:** ✅ COMPLETE (3/3)

---

## 6. ANALYTICS SERVICE (analytics-service) - Port 8006

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ❌ | GET | /api/v1/dashboard/metrics | get_dashboard_metrics (CRITICAL!) |
| ❌ | GET | /api/v1/dashboard/activity | get_recent_activity (CRITICAL!) |
| ❌ | GET | /api/v1/analytics/forecast | get_volume_forecast |
| ❌ | GET | /api/v1/analytics/sla-prediction/{ticket_id} | predict_sla_breach |
| ❌ | POST | /api/v1/ml/train | train_ml_models |
| ❌ | GET | /api/v1/analytics/team-performance | get_team_performance |
| ❌ | GET | /api/v1/ml/models/status | get_ml_models_status |
| ❌ | POST | /api/v1/ml/predict/category | predict_ticket_category |
| ❌ | POST | /api/v1/ml/predict/complexity | predict_ticket_complexity |
| ❌ | POST | /api/v1/ml/predict/resolution-time | predict_resolution_time |
| ❌ | POST | /api/v1/ml/predict/all | predict_all_ticket_attributes |

**Status:** ❌ CRITICAL - COMPLETELY MISSING (0/11)
**ALL ENDPOINTS NEED TO BE ADDED**

---

## 7. ESCALATION SERVICE (escalation-service) - Port 8007

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | POST | /api/v1/escalation/{ticket_id}/manual | manual_escalate |
| ✅ | GET | /api/v1/escalation/{ticket_id}/check | check_escalation_needed |
| ✅ | GET | /api/v1/escalation/{ticket_id}/history | get_escalation_history |

**Status:** ✅ COMPLETE (3/3)

---

## 8. COLLABORATION SERVICE (collaboration-service) - Port 8008

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | POST | /api/v1/collaboration/{ticket_id}/add | add_collaborator |
| ✅ | DELETE | /api/v1/collaboration/{ticket_id}/remove/{team_member_id} | remove_collaborator |
| ✅ | GET | /api/v1/collaboration/{ticket_id} | get_collaboration_summary |

**Status:** ✅ COMPLETE (3/3)

---

## 9. INTEGRATION SERVICE (integration-service) - Port 8009

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/redmine/group-members | get_redmine_group_members |
| ✅ | GET | /api/v1/redmine/user/{user_id} | get_redmine_user |
| ❌ | POST | /api/v1/redmine/sync-statuses | sync_redmine_statuses |

**Status:** ⚠️ INCOMPLETE (2/3)
**Missing:** sync_redmine_statuses

---

## 10. SCHEDULING SERVICE (scheduling-service) - Port 8010

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | GET | /api/v1/scheduling/shifts | list_shifts |
| ✅ | POST | /api/v1/scheduling/shifts | create_shift |
| ✅ | PUT | /api/v1/scheduling/shifts/{shift_id} | update_shift |
| ✅ | DELETE | /api/v1/scheduling/shifts/{shift_id} | delete_shift |
| ✅ | GET | /api/v1/scheduling/leaves | list_leaves |
| ✅ | GET | /api/v1/scheduling/leaves/me | list_my_leaves |
| ✅ | POST | /api/v1/scheduling/leaves | create_leave |
| ✅ | PUT | /api/v1/scheduling/leaves/{leave_id} | update_leave |
| ✅ | POST | /api/v1/scheduling/leaves/{leave_id}/status | update_leave_status |
| ✅ | DELETE | /api/v1/scheduling/leaves/{leave_id} | delete_leave |
| ✅ | GET | /api/v1/scheduling/oncall/rotation | get_oncall_rotation |
| ✅ | GET | /api/v1/scheduling/oncall/assignments | get_oncall_assignments |
| ✅ | POST | /api/v1/scheduling/oncall/assignments/run | run_oncall_assignment |
| ✅ | GET | /api/v1/scheduling/oncall/rotate | rotate_oncall_from_link |
| ✅ | POST | /api/v1/scheduling/oncall/assignments/{assignment_id}/replace | replace_oncall_assignment |
| ❌ | GET | /api/v1/scheduler/status | get_scheduler_status |

**Status:** ⚠️ INCOMPLETE (15/16)
**Missing:** get_scheduler_status

---

## 11. WORK SESSION SERVICE (work-session-service) - Port 8011

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ✅ | POST | /api/v1/tickets/{ticket_id}/work/start | start_work_session |
| ✅ | POST | /api/v1/tickets/{ticket_id}/work/pause | pause_work_session |
| ✅ | POST | /api/v1/tickets/{ticket_id}/work/resume | resume_work_session |
| ✅ | GET | /api/v1/tickets/{ticket_id}/work/summary | get_work_summary |
| ✅ | GET | /api/v1/work/active | get_active_sessions_for_member |

**Status:** ✅ COMPLETE (5/5)

---

## 12. MISSING SERVICE - ACTIVITIES/AUDIT LOG

| Status | Method | Endpoint | Function |
|--------|--------|----------|----------|
| ❌ | GET | /api/v1/activities | get_activities |
| ❌ | GET | /api/v1/activities/ticket/{ticket_id} | get_ticket_activities |

**Recommendation:** Add to ticket-service OR create new activity-service

---

## 13. INFRASTRUCTURE/UTILITY ENDPOINTS

| Status | Method | Endpoint | Service | Function |
|--------|--------|----------|---------|----------|
| ✅ | GET | /health | All services | Health check |
| ❌ | GET | / | ? | Root endpoint |
| ❌ | GET | /api/v1/metrics/cache | ? | Cache metrics |
| ❌ | DELETE | /api/v1/cache/clear | ? | Clear cache |
| ❌ | WEBSOCKET | /ws/ticket/{ticket_id} | ? | Real-time updates |

---

## SUMMARY

### By Service:
| Service | Complete | Incomplete | Missing | Total |
|---------|----------|------------|---------|-------|
| Auth | 10 | 0 | 0 | 10 |
| Ticket | 7 | 0 | 4 | 11 |
| Team | 7 | 0 | 1 | 8 |
| SLA | 7 | 0 | 0 | 7 |
| Workload | 3 | 0 | 0 | 3 |
| Analytics | 0 | 0 | 11 | 11 |
| Escalation | 3 | 0 | 0 | 3 |
| Collaboration | 3 | 0 | 0 | 3 |
| Integration | 2 | 0 | 1 | 3 |
| Scheduling | 15 | 0 | 1 | 16 |
| Work Session | 5 | 0 | 0 | 5 |
| Activities | 0 | 0 | 2 | 2 |

### Overall:
- **✅ Complete:** 62 endpoints
- **❌ Missing:** 20 endpoints
- **Total:** 82 endpoints

### Critical Missing (Priority 1):
1. ❌ /api/v1/dashboard/metrics
2. ❌ /api/v1/dashboard/activity
3. ❌ All 11 Analytics/ML endpoints

### High Priority Missing (Priority 2):
4. ❌ /api/v1/tickets/{id}/resolve
5. ❌ /api/v1/tickets/process
6. ❌ /api/v1/activities (both endpoints)
7. ❌ /api/v1/team/members/{id}/performance

### Medium Priority Missing (Priority 3):
8. ❌ /api/v1/redmine/sync-statuses
9. ❌ /api/v1/scheduler/status
10. ❌ WebSocket support
11. ❌ Cache/metrics endpoints

---

## IMPLEMENTATION PLAN

### Phase 1: CRITICAL - Analytics Service (4-6 hours)
Add all 11 missing endpoints to analytics-service:
- Dashboard metrics & activity
- ML predictions (category, complexity, resolution-time, all)
- Forecasting
- SLA prediction
- Team performance
- ML model status & training

### Phase 2: HIGH - Ticket Service (2-3 hours)
Add missing ticket operations:
- create_ticket
- process_tickets
- resolve_ticket

### Phase 3: HIGH - Activities (2 hours)
Add activity/audit log endpoints to ticket-service

### Phase 4: MEDIUM - Remaining Endpoints (2 hours)
- team/members/{id}/performance
- redmine/sync-statuses
- scheduler/status

### Phase 5: OPTIONAL - Infrastructure (4+ hours)
- WebSocket support
- Cache management endpoints

**TOTAL ESTIMATED TIME: 14-17 hours of development**
