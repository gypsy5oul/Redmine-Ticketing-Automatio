#!/usr/bin/env python3
"""
DevOps Ticket Management System v3.0 - Main Application
FastAPI backend with WebSocket support
"""

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict
import logging

from app.core.config import settings
from app.core.database import get_db, init_db, close_db
from app.api.deps import get_current_user, require_admin
from pydantic import BaseModel, Field
from app.services import (
    TicketProcessor,
    SLAManager,
    WorkloadManager,
    EscalationService,
    NotificationService,
    CollaborationService,
    MLPredictionService,
    RedmineService,
    WorkSessionService
)
from app.models.filter import SavedTicketFilter

# Configure logging
from loguru import logger
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL
)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise DevOps Ticket Management with AI and ML",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication router
from app.api.v1 import auth as auth_router
from app.api.v1 import scheduling as scheduling_router
from app.api.v1 import work_sessions as work_sessions_router
from app.api.v1 import projects as projects_router
from app.api.deps import get_current_user_optional
from app.models.user import User, UserRole
app.include_router(auth_router.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(scheduling_router.router)
app.include_router(work_sessions_router.router)
app.include_router(projects_router.router)


class TicketResolutionRequest(BaseModel):
    """Request payload for resolving or closing a ticket."""

    resolution_notes: str = Field(
        ...,
        min_length=3,
        max_length=5000,
        description="Detailed resolution notes that will be stored and pushed to Redmine.",
    )
    close_ticket: bool = Field(
        default=False,
        description="Whether to mark the ticket as fully closed in addition to resolved.",
    )


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()

    # Start background scheduler (only if enabled)
    if settings.ENABLE_SCHEDULER:
        logger.info("📅 Scheduler is ENABLED - Starting background jobs...")
        from app.scheduler.scheduler import start_scheduler
        start_scheduler()
    else:
        logger.info("📅 Scheduler is DISABLED - Running in API-only mode")

    logger.info("✅ Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down application...")
    await close_db()

    if settings.ENABLE_SCHEDULER:
        from app.scheduler.scheduler import stop_scheduler
        stop_scheduler()

    logger.info("✅ Shutdown complete")


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/", tags=["Info"])
async def root():
    """API information"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Info"])
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check"""
    try:
        # Test database (SQLAlchemy 2.0 compatible)
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Test Redis
    from app.core.database import redis_client
    try:
        redis_client.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if db_status == "healthy" and redis_status == "healthy" else "degraded"

    return {
        "overall_status": overall_status,
        "components": {
            "database": db_status,
            "redis": redis_status
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/metrics/cache", tags=["Info"])
async def get_cache_metrics(db: Session = Depends(get_db)):
    """Get comprehensive cache performance metrics"""
    from app.services.llm_service import EnhancedLLMService
    from app.services.query_optimizer import QueryOptimizer

    llm_service = EnhancedLLMService()
    llm_stats = llm_service.get_cache_stats()

    query_optimizer = QueryOptimizer(db)
    query_stats = query_optimizer.get_cache_stats()

    # Get Redis info
    from app.core.database import redis_client
    try:
        redis_info = redis_client.info('memory')
        cache_size_mb = round(redis_info.get('used_memory', 0) / 1024 / 1024, 2)
        redis_keys = redis_client.dbsize()
    except:
        cache_size_mb = 0
        redis_keys = 0

    return {
        "llm_cache": llm_stats,
        "query_cache": query_stats,
        "redis": {
            "memory_mb": cache_size_mb,
            "total_keys": redis_keys
        },
        "timestamp": datetime.now().isoformat()
    }


@app.delete("/api/v1/cache/clear", tags=["Info"])
async def clear_cache(cache_type: str = "all", db: Session = Depends(get_db)):
    """
    Clear cache by type

    Args:
        cache_type: Type of cache to clear (llm, query, sla, workload, all)
    """
    from app.core.database import redis_client
    from app.services.query_optimizer import QueryOptimizer

    query_optimizer = QueryOptimizer(db)

    patterns = {
        "llm": "llm:cache:*",
        "query": "query:*",
        "sla": "sla:*",
        "workload": "workload:*",
        "all": "*"
    }

    if cache_type not in patterns:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cache_type. Must be one of: {list(patterns.keys())}"
        )

    try:
        if cache_type == "query":
            query_optimizer.invalidate_cache()
        else:
            pattern = patterns[cache_type]
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                redis_client.delete(*keys)

        return {
            "success": True,
            "cache_type": cache_type,
            "pattern": patterns[cache_type],
            "cleared_at": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TICKET PROCESSING ENDPOINTS
# ============================================================================

@app.get("/api/v1/tickets", tags=["Tickets"])
async def get_tickets(
    request: Request,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    team_level: Optional[str] = None,
    sla_status: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    ticket_number: Optional[str] = None,
    filter_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    List tickets with optional filtering

    Query params:
    - status: Filter by status (new, assigned, in_progress, resolved, closed)
    - priority: Filter by priority (P1, P2, P3, P4, P5)
    - team_level: Filter by team level (L1, L2, L3)
    - sla_status: Filter by SLA status (within_sla, at_risk, critical, breached)
    - limit: Max records to return (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        from sqlalchemy import or_, func
        from app.models.ticket import TicketHistory, TicketStatus, TicketPriority, TicketCategory, ComplexityLevel
        from app.models.team import TeamLevel
        from app.models.sla import SLATracker, SLAStatus
        from app.models.filter import SavedTicketFilter

        query_params = request.query_params

        def normalize_priority(value: str) -> Optional[TicketPriority]:
            if not value:
                return None
            normalized = value.strip()
            alias = {
                "P1": "P1(Critical)",
                "P1CRITICAL": "P1(Critical)",
                "P2": "P2(High)",
                "P2HIGH": "P2(High)",
                "P3": "P3(Medium)",
                "P4": "P4(Low)",
                "P5": "P5(Trivial)",
            }
            lookup_key = normalized.upper().replace(" ", "")
            resolved = alias.get(lookup_key, normalized)
            try:
                return TicketPriority(resolved)
            except ValueError:
                logger.debug(f"Unknown priority filter '{value}' ignored")
                return None

        def parse_datetime(raw: Optional[str]) -> Optional[datetime]:
            if not raw:
                return None
            try:
                if raw.endswith("Z"):
                    raw = raw.replace("Z", "+00:00")
                return datetime.fromisoformat(raw)
            except ValueError:
                logger.debug(f"Invalid datetime '{raw}' ignored")
                return None

        # Aggregate filters from query params and optional saved filter
        filters_payload = {
            "statuses": [],
            "priorities": [],
            "team_levels": [],
            "sla_statuses": [],
            "assigned_to_ids": [],
            "categories": [],
            "created_from": None,
            "created_to": None,
            "ticket_number": None,
        }

        # merge helper
        def extend_filter(key: str, values: List[Any]):
            existing = filters_payload.setdefault(key, [])
            for value in values:
                if value not in existing:
                    existing.append(value)

        extend_filter("statuses", [status] if status else [])
        extend_filter("priorities", [priority] if priority else [])
        extend_filter("team_levels", [team_level] if team_level else [])
        extend_filter("sla_statuses", [sla_status] if sla_status else [])
        if assigned_to_id:
            extend_filter("assigned_to_ids", [assigned_to_id])
        if created_from:
            filters_payload["created_from"] = created_from
        if created_to:
            filters_payload["created_to"] = created_to
        if ticket_number:
            filters_payload["ticket_number"] = ticket_number

        extend_filter("statuses", query_params.getlist("status"))
        extend_filter("priorities", query_params.getlist("priority"))
        extend_filter("team_levels", query_params.getlist("team_level"))
        extend_filter("sla_statuses", query_params.getlist("sla_status"))
        extend_filter("assigned_to_ids", [int(v) for v in query_params.getlist("assigned_to_id") if v.isdigit()])
        extend_filter("categories", query_params.getlist("category"))

        if query_params.get("categories"):
            extend_filter("categories", query_params.getlist("categories"))

        saved_filters_applied = None
        if filter_id or query_params.get("filter_id"):
            saved_id = filter_id or int(query_params.get("filter_id"))
            saved_filter = db.query(SavedTicketFilter).filter(SavedTicketFilter.id == saved_id).first()
            if not saved_filter:
                raise HTTPException(status_code=404, detail="Saved filter not found")
            saved_filters_applied = {
                "id": saved_filter.id,
                "name": saved_filter.name,
                "description": saved_filter.description,
            }
            payload = saved_filter.filters or {}
            extend_filter("statuses", payload.get("statuses", []))
            extend_filter("priorities", payload.get("priorities", []))
            extend_filter("team_levels", payload.get("team_levels", []))
            extend_filter("sla_statuses", payload.get("sla_statuses", []))
            extend_filter("assigned_to_ids", payload.get("assigned_to_ids", []))
            extend_filter("categories", payload.get("categories", []))
            filters_payload["created_from"] = filters_payload["created_from"] or payload.get("created_from")
            filters_payload["created_to"] = filters_payload["created_to"] or payload.get("created_to")

        status_filters: List[TicketStatus] = []
        for status_value in filters_payload["statuses"]:
            try:
                status_filters.append(TicketStatus(status_value))
            except ValueError:
                logger.debug(f"Unknown status filter '{status_value}' ignored")

        priority_filters: List[TicketPriority] = []
        for priority_value in filters_payload["priorities"]:
            normalized_priority = normalize_priority(priority_value)
            if normalized_priority:
                priority_filters.append(normalized_priority)

        team_level_filters = [
            level for level in filters_payload["team_levels"]
            if level in {"L1", "L2", "L3"}
        ]

        category_filters: List[TicketCategory] = []
        for category_value in filters_payload["categories"]:
            if not category_value:
                continue
            normalized_category = category_value.lower()
            try:
                category_filters.append(TicketCategory(normalized_category))
            except ValueError:
                logger.debug(f"Unknown category filter '{category_value}' ignored")

        assigned_to_filters: List[int] = []
        for raw_id in filters_payload["assigned_to_ids"]:
            try:
                assigned_to_filters.append(int(raw_id))
            except (TypeError, ValueError):
                logger.debug(f"Invalid assignee '{raw_id}' ignored")

        created_from_dt = parse_datetime(filters_payload.get("created_from"))
        created_to_dt = parse_datetime(filters_payload.get("created_to"))

        sla_filters = [value.lower() for value in filters_payload["sla_statuses"] if value]

        filters = []
        need_sla_join = False

        if status_filters:
            filters.append(TicketHistory.status.in_(status_filters))

        if priority_filters:
            filters.append(TicketHistory.priority.in_(priority_filters))

        if team_level_filters:
            filters.append(TicketHistory.team_level.in_(team_level_filters))

        if category_filters:
            filters.append(TicketHistory.category.in_(category_filters))

        if assigned_to_filters:
            filters.append(TicketHistory.assigned_to_id.in_(assigned_to_filters))

        if created_from_dt:
            filters.append(TicketHistory.created_at >= created_from_dt)
        if created_to_dt:
            filters.append(TicketHistory.created_at <= created_to_dt)

        # Filter by ticket number (redmine_ticket_id)
        ticket_number_param = filters_payload.get("ticket_number")
        if ticket_number_param:
            try:
                ticket_num = int(str(ticket_number_param).strip())
                filters.append(TicketHistory.redmine_ticket_id == ticket_num)
            except (ValueError, TypeError):
                logger.debug(f"Invalid ticket number '{ticket_number_param}' ignored")

        if sla_filters:
            sla_conditions = []
            sla_map = {
                "within_sla": SLAStatus.WITHIN_SLA,
                "at_risk": SLAStatus.AT_RISK,
                "critical": SLAStatus.CRITICAL,
                "breached": SLAStatus.BREACHED,
            }
            for sla_value in sla_filters:
                if sla_value == "breached":
                    sla_conditions.append(TicketHistory.sla_breached == True)  # noqa: E712
                elif sla_value == "paused":
                    need_sla_join = True
                    sla_conditions.append(SLATracker.paused == True)  # noqa: E712
                elif sla_value == "met":
                    need_sla_join = True
                    sla_conditions.append(
                        (SLATracker.status == SLAStatus.WITHIN_SLA)
                        & TicketHistory.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])
                    )
                elif sla_value in sla_map:
                    need_sla_join = True
                    sla_conditions.append(SLATracker.status == sla_map[sla_value])
                else:
                    logger.debug(f"Unknown SLA filter '{sla_value}' ignored")

            if sla_conditions:
                filters.append(or_(*sla_conditions))

        base_query = db.query(TicketHistory)
        if need_sla_join:
            base_query = base_query.join(
                SLATracker,
                SLATracker.ticket_id == TicketHistory.id,
                isouter=True
            )

        # RBAC: Filter tickets for VIEWER role
        # VIEWER users can only see tickets assigned to them or where they're collaborating
        if current_user and current_user.role == UserRole.VIEWER:
            from app.models.team import TeamMember
            from app.models.ticket import TicketCollaboration

            # Find team_member linked to this user
            team_member = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).first()

            if team_member:
                # Allow tickets where user is assigned OR collaborating
                viewer_filter = or_(
                    TicketHistory.assigned_to_id == team_member.id,
                    TicketHistory.id.in_(
                        db.query(TicketCollaboration.ticket_id)
                        .filter(TicketCollaboration.team_member_id == team_member.id)
                        .filter(TicketCollaboration.is_active == True)  # noqa: E712
                    )
                )
                filters.append(viewer_filter)
            else:
                # User has no team_member, show no tickets
                filters.append(TicketHistory.id == -1)

        filtered_query = base_query.filter(*filters)

        total = filtered_query.distinct(TicketHistory.id).count()

        tickets = (
            filtered_query
            .order_by(TicketHistory.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Backfill requester names if missing
        missing_requester_tickets = [ticket for ticket in tickets if not ticket.requester_name]
        if missing_requester_tickets:
            from app.services.redmine_service import RedmineService

            redmine_service = RedmineService()
            updated = False

            logger.info(
                "ℹ️ Requester names missing for %d tickets - attempting backfill",
                len(missing_requester_tickets),
            )

            for ticket_record in missing_requester_tickets:
                issue = redmine_service.get_issue(ticket_record.redmine_ticket_id)
                if not issue:
                    continue
                author = issue.get("author") or {}
                author_name = author.get("name")
                if author_name and ticket_record.requester_name != author_name:
                    ticket_record.requester_name = author_name
                    updated = True

            if updated:
                try:
                    db.flush()
                    db.commit()
                except Exception as commit_error:
                    db.rollback()
                    logger.warning(
                        "⚠️ Failed to backfill requester names: %s",
                        commit_error,
                    )
                else:
                    logger.debug(
                        "✅ Backfilled requester names for %d tickets",
                        len(missing_requester_tickets),
                    )

        # Fetch SLA trackers for all tickets in single query (avoid N+1)
        ticket_ids = [t.id for t in tickets]
        sla_trackers_query = (
            db.query(SLATracker).filter(SLATracker.ticket_id.in_(ticket_ids)).all()
            if ticket_ids
            else []
        )
        sla_by_ticket = {sla.ticket_id: sla for sla in sla_trackers_query}

        from app.models.work_session import WorkSession, SessionType

        active_session_by_ticket = {}
        if ticket_ids:
            active_sessions = (
                db.query(WorkSession)
                .filter(
                    WorkSession.ticket_id.in_(ticket_ids),
                    WorkSession.is_active.is_(True)
                )
                .all()
            )
            for session in active_sessions:
                existing = active_session_by_ticket.get(session.ticket_id)
                if not existing:
                    active_session_by_ticket[session.ticket_id] = session
                    continue

                existing_priority = 0 if existing.session_type == SessionType.ACTIVE_WORK else 1
                new_priority = 0 if session.session_type == SessionType.ACTIVE_WORK else 1
                if new_priority < existing_priority:
                    active_session_by_ticket[session.ticket_id] = session

        def _enum_value(value):
            return value.value if hasattr(value, "value") else value

        status_breakdown = {
            _enum_value(status): count
            for status, count in (
                filtered_query
                .with_entities(TicketHistory.status, func.count(TicketHistory.id))
                .group_by(TicketHistory.status)
                .all()
            )
        }

        priority_breakdown = {
            _enum_value(priority): count
            for priority, count in (
                filtered_query
                .with_entities(TicketHistory.priority, func.count(TicketHistory.id))
                .group_by(TicketHistory.priority)
                .all()
            )
        }

        applied_filter_summary = {
            "statuses": [_enum_value(status) for status in status_filters],
            "priorities": [_enum_value(priority) for priority in priority_filters],
            "team_levels": team_level_filters,
            "sla_statuses": sla_filters,
            "assigned_to_ids": assigned_to_filters,
            "categories": [_enum_value(category) for category in category_filters],
            "created_from": created_from_dt.isoformat() if created_from_dt else None,
            "created_to": created_to_dt.isoformat() if created_to_dt else None,
        }

        # Fetch work summaries for all tickets (for analytics)
        work_summaries_by_ticket = {}
        if ticket_ids:
            from app.services.work_session_service import WorkSessionService
            work_session_service = WorkSessionService(db)
            for ticket_id in ticket_ids:
                work_summaries_by_ticket[ticket_id] = work_session_service.get_work_summary(ticket_id)

        # Fetch attachments from Redmine for all tickets
        attachments_by_redmine_id = {}
        if tickets:
            from app.services.redmine_service import RedmineService
            redmine_service = RedmineService()
            redmine_ticket_ids = [t.redmine_ticket_id for t in tickets]
            redmine_issues = redmine_service.get_issues_by_ids(redmine_ticket_ids)

            for redmine_id, issue_data in redmine_issues.items():
                raw_attachments = issue_data.get('attachments', [])
                attachments_by_redmine_id[redmine_id] = [
                    {
                        "id": att.get('id'),
                        "filename": att.get('filename'),
                        "filesize": att.get('filesize'),
                        "content_url": att.get('content_url'),
                        "content_type": att.get('content_type'),
                        "description": att.get('description'),
                        "created_on": att.get('created_on'),
                    }
                    for att in raw_attachments
                ]

        return {
            "tickets": [
                {
                    "id": t.id,
                    "redmine_ticket_id": t.redmine_ticket_id,
                    "subject": t.subject,
                    "description": t.description,
                    "attachments": attachments_by_redmine_id.get(t.redmine_ticket_id, []),
                    "priority": _enum_value(t.priority),
                    "status": _enum_value(t.status),
                    "requester_name": t.requester_name,
                    "sla_tracker": {
                        "id": sla_by_ticket[t.id].id,
                        "status": _enum_value(sla_by_ticket[t.id].status),
                        "time_remaining_minutes": sla_by_ticket[t.id].calculate_time_remaining("resolution"),
                        "completion_percentage": sla_by_ticket[t.id].get_completion_percentage("resolution"),
                        "paused": sla_by_ticket[t.id].paused,
                        "resolution_deadline": sla_by_ticket[t.id].resolution_deadline.isoformat() if sla_by_ticket[t.id].resolution_deadline else None,
                    } if t.id in sla_by_ticket else None,
                    "category": _enum_value(t.category) if t.category else None,
                    "complexity": _enum_value(t.complexity) if t.complexity else None,
                    "team_level": t.team_level,
                    "assigned_to_id": t.assigned_to_id,
                    "assigned_to": {
                        "id": t.assigned_to.id,
                        "name": t.assigned_to.name
                    } if t.assigned_to else None,
                    "sla_breached": t.sla_breached,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                    "last_work_session_at": t.last_work_session_at.isoformat() if t.last_work_session_at else None,
                    "total_work_minutes": int(t.total_work_minutes or 0),
                    "total_waiting_minutes": int(t.total_waiting_minutes or 0),
                    "total_idle_minutes": int(t.total_idle_minutes or 0),
                    "work_efficiency_percent": round(t.work_efficiency_percent, 2) if t.work_efficiency_percent is not None else None,
                    "resolution_notes": t.resolution_notes,
                    "active_session": (
                        {
                            "id": active_session.id,
                            "type": _enum_value(active_session.session_type),
                            "team_member_id": active_session.team_member_id,
                            "started_at": active_session.started_at.isoformat() if active_session.started_at else None,
                        }
                        if (active_session := active_session_by_ticket.get(t.id))
                        else None
                    ),
                    "work_summary": work_summaries_by_ticket.get(t.id)
                }
                for t in tickets
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "filters": applied_filter_summary,
            "saved_filter": saved_filters_applied,
            "status_breakdown": status_breakdown,
            "priority_breakdown": priority_breakdown
        }

    except Exception as e:
        logger.exception("❌ Failed to fetch tickets")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tickets/process", tags=["Tickets"])
async def process_tickets(db: Session = Depends(get_db)):
    """
    🚀 Main endpoint - Process all new tickets

    Pipeline:
    1. Fetch from Redmine
    2. AI analysis
    3. ML routing
    4. SLA tracking
    5. Notifications
    """
    try:
        processor = TicketProcessor(db)
        result = processor.process_new_tickets()
        return result
    except Exception as e:
        logger.error(f"❌ Process tickets failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-tickets", tags=["Tickets - Legacy"])
async def process_tickets_legacy(db: Session = Depends(get_db)):
    """
    🔄 Legacy endpoint - Redirects to /api/v1/tickets/process

    DEPRECATED: Use /api/v1/tickets/process instead
    This endpoint exists for backward compatibility
    """
    try:
        processor = TicketProcessor(db)
        result = processor.process_new_tickets()
        logger.warning("⚠️ Legacy endpoint /process-tickets called - please update to /api/v1/tickets/process")
        return result
    except Exception as e:
        logger.error(f"❌ Process tickets failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tickets/{ticket_id}/resolve", tags=["Tickets"])
async def resolve_ticket(
    ticket_id: int,
    payload: TicketResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a ticket with mandatory resolution notes (optionally closing it)."""

    from datetime import datetime, timezone
    from app.models.ticket import TicketHistory, TicketStatus, TicketComment, CommentType
    from app.models.team import TeamMember
    from app.models.sla import SLATracker, SLAStatus

    ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
        raise HTTPException(status_code=400, detail="Ticket is already resolved or closed")

    team_member = (
        db.query(TeamMember)
        .filter(TeamMember.user_id == current_user.id)
        .first()
    )

    is_privileged = current_user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}

    if not is_privileged:
        if not team_member or ticket.assigned_to_id != team_member.id:
            raise HTTPException(
                status_code=403,
                detail="You must be the assigned engineer to resolve this ticket",
            )

    acting_member_id = team_member.id if team_member else ticket.assigned_to_id

    work_session_service = WorkSessionService(db)

    try:
        work_session_service.end_work_session(
            ticket_id=ticket.id,
            member_id=acting_member_id,
            notes=payload.resolution_notes,
        )
    except (ValueError, AttributeError) as session_error:  # pragma: no cover
        logger.warning(
            "⚠️ Failed to close active work sessions for ticket %s: %s",
            ticket_id,
            session_error,
        )
    except Exception as session_error:  # pragma: no cover
        logger.exception(
            "⚠️ Unexpected error closing work sessions for ticket %s",
            ticket_id,
        )

    db.expire_all()
    ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

    now = datetime.now(timezone.utc)
    ticket.status = TicketStatus.CLOSED if payload.close_ticket else TicketStatus.RESOLVED
    ticket.resolved_at = ticket.resolved_at or now
    if payload.close_ticket:
        ticket.closed_at = now
    ticket.resolution_notes = payload.resolution_notes

    tracker = db.query(SLATracker).filter(SLATracker.ticket_id == ticket.id).first()
    if tracker:
        tracker.actual_resolution_time = now
        if not tracker.resolution_breached:
            tracker.status = SLAStatus.WITHIN_SLA

    try:
        SLAManager(db).update_sla_status(ticket.id)
    except Exception as sla_error:  # pragma: no cover
        logger.warning("⚠️ Failed to refresh SLA status for ticket %s: %s", ticket.id, sla_error)

    if payload.resolution_notes:
        try:
            comment = TicketComment(
                ticket_id=ticket.id,
                author_id=acting_member_id,
                content=payload.resolution_notes,
                comment_type=CommentType.INTERNAL,
            )
            db.add(comment)
        except Exception as comment_error:  # pragma: no cover
            logger.warning("⚠️ Failed to store resolution comment: %s", comment_error)

    db.commit()
    db.refresh(ticket)

    try:
        status_id = 5 if payload.close_ticket else 3
        RedmineService().update_issue(
            ticket.redmine_ticket_id,
            status_id=status_id,
            notes=payload.resolution_notes,
        )
    except Exception as redmine_error:  # pragma: no cover
        logger.warning("⚠️ Failed to update Redmine for ticket %s: %s", ticket.redmine_ticket_id, redmine_error)

    ticket_payload = await get_ticket(ticket_id, db)

    return {
        "success": True,
        "ticket": ticket_payload,
    }


@app.get("/api/v1/tickets/{ticket_id}", tags=["Tickets"])
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get ticket details"""
    from app.models.ticket import TicketHistory
    ticket = db.query(TicketHistory).filter(
        TicketHistory.id == ticket_id
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    work_session_service = WorkSessionService(db)
    work_summary = work_session_service.get_work_summary(ticket_id)

    return {
        "id": ticket.id,
        "redmine_ticket_id": ticket.redmine_ticket_id,
        "subject": ticket.subject,
        "priority": ticket.priority.value,
        "status": ticket.status.value,
        "assigned_to": {
            "id": ticket.assigned_to.id,
            "name": ticket.assigned_to.name
        } if ticket.assigned_to else None,
        "assigned_to_id": ticket.assigned_to_id,
        "category": ticket.category.value if ticket.category else None,
        "complexity": ticket.complexity.value if ticket.complexity else None,
        "created_at": ticket.created_at.isoformat(),
        "assigned_at": ticket.assigned_at.isoformat() if ticket.assigned_at else None,
        "resolution_notes": ticket.resolution_notes,
        "total_work_minutes": int(ticket.total_work_minutes or 0),
        "total_waiting_minutes": int(ticket.total_waiting_minutes or 0),
        "total_idle_minutes": int(ticket.total_idle_minutes or 0),
        "work_efficiency_percent": round(ticket.work_efficiency_percent, 2) if ticket.work_efficiency_percent is not None else None,
        "last_work_session_at": ticket.last_work_session_at.isoformat() if ticket.last_work_session_at else None,
        "active_work_session_id": ticket.active_work_session_id,
        "work_summary": work_summary
    }


@app.put("/api/v1/tickets/{ticket_id}", tags=["Tickets"])
async def update_ticket(
    ticket_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Update ticket details

    Body can include:
    - status: Ticket status
    - priority: Ticket priority
    - assigned_to_id: User ID to assign to
    """
    try:
        from app.models.ticket import TicketHistory, TicketStatus, TicketPriority

        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        work_session_service = WorkSessionService(db)
        previous_assignee = ticket.assigned_to_id
        assignment_changed = False
        new_status = None

        if "assigned_to_id" in data:
            new_assignee = data["assigned_to_id"]
            if new_assignee != ticket.assigned_to_id:
                ticket.assigned_to_id = new_assignee
                assignment_changed = True

        if "status" in data:
            new_status = TicketStatus(data["status"])
            if new_status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
                raise HTTPException(
                    status_code=400,
                    detail="Use /api/v1/tickets/{ticket_id}/resolve to mark tickets as resolved or closed",
                )
            ticket.status = new_status

        if "priority" in data:
            ticket.priority = TicketPriority(data["priority"])

        if "resolution_notes" in data:
            ticket.resolution_notes = data["resolution_notes"]

        db.commit()
        db.refresh(ticket)

        try:
            if assignment_changed and ticket.assigned_to_id:
                work_session_service.handle_assignment_change(
                    ticket,
                    ticket.assigned_to_id,
                    previous_assignee,
                )
            elif ticket.assigned_to_id and new_status == TicketStatus.ASSIGNED:
                work_session_service.ensure_idle_session(ticket.id, ticket.assigned_to_id)

            if new_status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
                target_member = ticket.assigned_to_id or previous_assignee
                if target_member:
                    work_session_service.end_work_session(ticket.id, target_member)
        except Exception as tracking_error:
            logger.warning("⚠️ Work session update failed for ticket %s: %s", ticket.id, tracking_error)

        return {
            "success": True,
            "ticket": {
                "id": ticket.id,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "assigned_to_id": ticket.assigned_to_id
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TICKET COMMENTS ENDPOINTS
# ============================================================================

@app.get("/api/v1/tickets/{ticket_id}/comments", tags=["Comments"])
async def get_ticket_comments(
    ticket_id: int,
    comment_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get all comments for a ticket

    Args:
        ticket_id: Ticket ID
        comment_type: Filter by comment type (public, internal)
    """
    try:
        from app.models.ticket import TicketHistory, TicketComment
        from app.models.team import TeamMember

        # Verify ticket exists
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Query comments
        query = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id)

        if comment_type:
            from app.models.ticket import CommentType as CommentTypeEnum
            query = query.filter(TicketComment.comment_type == CommentTypeEnum(comment_type))

        comments = query.order_by(TicketComment.created_at.asc()).all()

        # Build response with author names
        comments_data = []
        for comment in comments:
            author_name = None
            if comment.author_id:
                author = db.query(TeamMember).filter(TeamMember.id == comment.author_id).first()
                if author:
                    author_name = author.name

            comments_data.append({
                "id": comment.id,
                "ticket_id": comment.ticket_id,
                "author_id": comment.author_id,
                "author_name": author_name,
                "content": comment.content,
                "comment_type": comment.comment_type.value,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
                "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                "edited": comment.edited,
                "has_attachments": comment.has_attachments,
                "attachment_count": comment.attachment_count
            })

        return {
            "comments": comments_data,
            "total": len(comments_data),
            "ticket_id": ticket_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch comments for ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tickets/{ticket_id}/comments", tags=["Comments"])
async def create_comment(
    ticket_id: int,
    content: str,
    author_id: int,
    comment_type: str = "public",
    db: Session = Depends(get_db)
):
    """
    Create a new comment on a ticket

    Args:
        ticket_id: Ticket ID
        content: Comment content
        author_id: Team member ID who is creating the comment
        comment_type: Comment visibility (public or internal)
    """
    try:
        from app.models.ticket import TicketHistory, TicketComment, CommentType as CommentTypeEnum
        from app.models.team import TeamMember

        # Verify ticket exists
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Verify author exists
        author = db.query(TeamMember).filter(TeamMember.id == author_id).first()
        if not author:
            raise HTTPException(status_code=404, detail="Author not found")

        # Validate comment type
        if comment_type not in ["public", "internal"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid comment_type. Must be 'public' or 'internal'"
            )

        # Convert to enum
        comment_type_enum = CommentTypeEnum(comment_type)

        # Create comment
        comment = TicketComment(
            ticket_id=ticket_id,
            author_id=author_id,
            content=content,
            comment_type=comment_type_enum,
            edited=False,
            has_attachments=False,
            attachment_count=0
        )

        db.add(comment)
        db.commit()
        db.refresh(comment)

        logger.info(f"✅ Comment created on ticket {ticket_id} by {author.name}")

        return {
            "success": True,
            "comment": {
                "id": comment.id,
                "ticket_id": comment.ticket_id,
                "author_id": comment.author_id,
                "author_name": author.name,
                "content": comment.content,
                "comment_type": comment.comment_type.value,
                "created_at": comment.created_at.isoformat() if comment.created_at else None,
                "edited": comment.edited
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/comments/{comment_id}", tags=["Comments"])
async def update_comment(
    comment_id: int,
    content: str,
    db: Session = Depends(get_db)
):
    """
    Update an existing comment

    Args:
        comment_id: Comment ID
        content: Updated comment content
    """
    try:
        from app.models.ticket import TicketComment
        from datetime import datetime

        comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        # Update comment
        comment.content = content
        comment.edited = True
        comment.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(comment)

        logger.info(f"✅ Comment {comment_id} updated")

        return {
            "success": True,
            "comment": {
                "id": comment.id,
                "content": comment.content,
                "edited": comment.edited,
                "updated_at": comment.updated_at.isoformat() if comment.updated_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/comments/{comment_id}", tags=["Comments"])
async def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a comment

    Args:
        comment_id: Comment ID
    """
    try:
        from app.models.ticket import TicketComment

        comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()
        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        ticket_id = comment.ticket_id
        db.delete(comment)
        db.commit()

        logger.info(f"✅ Comment {comment_id} deleted from ticket {ticket_id}")

        return {
            "success": True,
            "message": "Comment deleted successfully",
            "comment_id": comment_id,
            "ticket_id": ticket_id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SLA MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/sla/policies", tags=["SLA"])
async def get_sla_policies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all SLA policies - Requires authentication"""
    try:
        from app.models.sla import SLAPolicy

        policies = db.query(SLAPolicy).all()

        return {
            "policies": [
                {
                    "id": p.id,
                    "priority": p.priority,
                    "environment": p.environment,
                    "response_time_minutes": p.response_time_minutes,
                    "resolution_time_minutes": p.resolution_time_minutes,
                    "escalation_time_minutes": p.escalation_time_minutes,
                    "business_hours_only": p.business_hours_only,
                    "active": p.active
                }
                for p in policies
            ],
            "total": len(policies)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch SLA policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sla/policies", tags=["SLA"])
async def create_sla_policy(
    priority: str,
    response_time_minutes: int = 30,
    resolution_time_minutes: int = 240,
    escalation_time_minutes: int = 180,
    environment: Optional[str] = None,
    business_hours_only: bool = True,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new SLA policy - Requires admin authentication"""
    try:
        from app.models.sla import SLAPolicy

        # Check if policy for this priority+environment already exists
        existing = db.query(SLAPolicy).filter(
            SLAPolicy.priority == priority,
            SLAPolicy.environment == environment
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"SLA policy for {priority}/{environment or 'all'} already exists"
            )

        policy = SLAPolicy(
            priority=priority,
            environment=environment,
            response_time_minutes=response_time_minutes,
            resolution_time_minutes=resolution_time_minutes,
            escalation_time_minutes=escalation_time_minutes,
            business_hours_only=business_hours_only,
            active=True
        )

        db.add(policy)
        db.commit()
        db.refresh(policy)

        return {
            "success": True,
            "policy": {
                "id": policy.id,
                "priority": policy.priority,
                "environment": policy.environment,
                "response_time_minutes": policy.response_time_minutes,
                "resolution_time_minutes": policy.resolution_time_minutes,
                "business_hours_only": policy.business_hours_only
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create SLA policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/sla/policies/{policy_id}", tags=["SLA"])
async def update_sla_policy(
    policy_id: int,
    policy_data: dict,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update an SLA policy - Requires admin authentication"""
    try:
        from app.models.sla import SLAPolicy

        policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="SLA policy not found")

        if 'response_time_minutes' in policy_data:
            policy.response_time_minutes = policy_data['response_time_minutes']
        if 'resolution_time_minutes' in policy_data:
            policy.resolution_time_minutes = policy_data['resolution_time_minutes']
        if 'escalation_time_minutes' in policy_data:
            policy.escalation_time_minutes = policy_data['escalation_time_minutes']
        if 'business_hours_only' in policy_data:
            policy.business_hours_only = policy_data['business_hours_only']
        if 'active' in policy_data:
            policy.active = policy_data['active']

        db.commit()
        db.refresh(policy)

        return {
            "success": True,
            "policy": {
                "id": policy.id,
                "priority": policy.priority,
                "response_time_minutes": policy.response_time_minutes,
                "resolution_time_minutes": policy.resolution_time_minutes,
                "business_hours_only": policy.business_hours_only,
                "active": policy.active
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update SLA policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sla/status/{ticket_id}", tags=["SLA"])
async def get_sla_status(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get SLA status for a ticket - Requires authentication"""
    sla_manager = SLAManager(db)
    status = sla_manager.get_sla_status(ticket_id)
    return status


@app.get("/api/v1/sla/at-risk", tags=["SLA"])
async def get_at_risk_tickets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tickets at risk of SLA breach - Requires authentication"""
    try:
        from app.models.sla import SLATracker, SLAStatus
        from app.models.ticket import TicketHistory

        # Get SLA trackers that are at risk or critical
        trackers = db.query(SLATracker).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL])
        ).all()

        # Build response with fields aligned to frontend expectations
        tickets = []
        for tracker in trackers:
            ticket = db.query(TicketHistory).filter(
                TicketHistory.id == tracker.ticket_id
            ).first()

            if ticket:
                # Calculate time remaining for resolution
                time_remaining = tracker.calculate_time_remaining('resolution')
                completion = tracker.get_completion_percentage('resolution')

                tickets.append({
                    "id": tracker.id,
                    "status": tracker.status.value,
                    "time_remaining_minutes": time_remaining,
                    "completion_percentage": round(completion, 2),
                    "resolution_deadline": tracker.resolution_deadline.isoformat() if tracker.resolution_deadline else None,
                    "response_deadline": tracker.response_deadline.isoformat() if tracker.response_deadline else None,
                    "ticket": {
                        "id": ticket.id,
                        "redmine_ticket_id": ticket.redmine_ticket_id,
                        "subject": ticket.subject,
                        "priority": ticket.priority.value,
                        "status": ticket.status.value,
                        "assigned_to": {
                            "id": ticket.assigned_to.id,
                            "name": ticket.assigned_to.name
                        } if ticket.assigned_to else None
                    }
                })

        return {"tickets": tickets, "count": len(tickets)}

    except Exception as e:
        logger.error(f"❌ Failed to fetch at-risk tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sla/{ticket_id}/pause", tags=["SLA"])
async def pause_sla(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause SLA timer (e.g., waiting for customer) - Requires authentication"""
    sla_manager = SLAManager(db)
    sla_manager.pause_sla(ticket_id)
    return {"message": "SLA paused", "ticket_id": ticket_id}


@app.post("/api/v1/sla/{ticket_id}/resume", tags=["SLA"])
async def resume_sla(
    ticket_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume SLA timer - Requires authentication"""
    sla_manager = SLAManager(db)
    sla_manager.resume_sla(ticket_id)
    return {"message": "SLA resumed", "ticket_id": ticket_id}


# ============================================================================
# WORKLOAD & CAPACITY ENDPOINTS
# ============================================================================

@app.get("/api/v1/workload", tags=["Workload"])
async def get_team_workload(
    team_level: Optional[str] = None,
    level: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get team workload"""
    workload_manager = WorkloadManager(db)
    effective_level = level or team_level
    workload_data = workload_manager.get_team_workload(effective_level)

    # Transform to match frontend WorkloadSummary type
    workload = [
        {
            "member_id": w["user_id"],
            "member_name": w["name"],
            "team_level": w["team_level"].value if hasattr(w["team_level"], "value") else w["team_level"],
            "current_tickets": w["current_tickets"],
            "max_tickets": w["max_tickets"],
            "capacity_percentage": w["utilization"],  # Rename utilization to capacity_percentage
            "is_available": w["is_available"]
        }
        for w in workload_data
    ]

    return {"workload": workload, "count": len(workload)}


@app.get("/api/v1/workload/capacity", tags=["Workload"])
async def get_capacity_summary(db: Session = Depends(get_db)):
    """Get overall capacity summary"""
    workload_manager = WorkloadManager(db)
    summary = workload_manager.get_capacity_summary()
    return summary


@app.get("/api/v1/workload/alerts", tags=["Workload"])
async def get_capacity_alerts(db: Session = Depends(get_db)):
    """Get capacity-related alerts"""
    workload_manager = WorkloadManager(db)
    alerts = workload_manager.check_capacity_alerts()
    return {"alerts": alerts, "count": len(alerts)}


# ============================================================================
# ESCALATION ENDPOINTS
# ============================================================================

@app.post("/api/v1/escalation/{ticket_id}/manual", tags=["Escalation"])
async def manual_escalate(
    ticket_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Manually escalate a ticket

    Body:
    {
        "to_team_level": "L2" or "L3",
        "to_member_id": optional member ID,
        "reason": "reason_code",
        "notes": "escalation notes"
    }
    """
    try:
        to_team_level = data.get("to_team_level")
        reason = data.get("reason", "manual_request")
        notes = data.get("notes", "")
        escalated_by = data.get("escalated_by", "System")  # TODO: Get from auth

        if not to_team_level:
            raise HTTPException(status_code=400, detail="to_team_level is required")

        escalation_service = EscalationService(db)
        escalation = escalation_service.manual_escalate(
            ticket_id=ticket_id,
            to_level=to_team_level,
            reason=reason,
            description=notes,
            escalated_by=escalated_by
        )

        if not escalation:
            raise HTTPException(status_code=400, detail="Escalation failed")

        return {
            "success": True,
            "escalation_id": escalation.id,
            "from_level": escalation.from_team_level,
            "to_level": escalation.to_team_level
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Manual escalation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/escalation/{ticket_id}/check", tags=["Escalation"])
async def check_escalation_needed(ticket_id: int, db: Session = Depends(get_db)):
    """Check if ticket needs escalation"""
    escalation_service = EscalationService(db)
    result = escalation_service.check_escalation_needed(ticket_id)
    return result


@app.get("/api/v1/escalation/{ticket_id}/history", tags=["Escalation"])
async def get_escalation_history(ticket_id: int, db: Session = Depends(get_db)):
    """Get escalation history for a ticket"""
    escalation_service = EscalationService(db)
    history = escalation_service.get_escalation_history(ticket_id)
    return {
        "ticket_id": ticket_id,
        "escalations": [
            {
                "id": e.id,
                "from_level": e.from_team_level,
                "to_level": e.to_team_level,
                "reason": e.reason.value,
                "escalated_at": e.escalated_at.isoformat()
            }
            for e in history
        ]
    }


# ============================================================================
# COLLABORATION ENDPOINTS
# ============================================================================

@app.post("/api/v1/collaboration/{ticket_id}/add", tags=["Collaboration"])
async def add_collaborator(
    ticket_id: int,
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Add collaborator to ticket

    Body:
    {
        "team_member_id": 123,
        "role": "secondary" (optional)
    }
    """
    try:
        team_member_id = data.get("team_member_id")
        role = data.get("role", "secondary")

        if not team_member_id:
            raise HTTPException(status_code=400, detail="team_member_id is required")

        collab_service = CollaborationService(db)
        collaboration = collab_service.add_collaborator(ticket_id, team_member_id, role)

        if not collaboration:
            raise HTTPException(status_code=400, detail="Failed to add collaborator")

        return {"success": True, "collaboration_id": collaboration.id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to add collaborator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/collaboration/{ticket_id}/remove/{team_member_id}", tags=["Collaboration"])
async def remove_collaborator(
    ticket_id: int,
    team_member_id: int,
    db: Session = Depends(get_db)
):
    """Remove collaborator from ticket"""
    collab_service = CollaborationService(db)
    success = collab_service.remove_collaborator(ticket_id, team_member_id)

    if not success:
        raise HTTPException(status_code=400, detail="Failed to remove collaborator")

    return {"success": True}


@app.get("/api/v1/collaboration/{ticket_id}", tags=["Collaboration"])
async def get_collaboration_summary(ticket_id: int, db: Session = Depends(get_db)):
    """Get collaboration summary for ticket"""
    collab_service = CollaborationService(db)
    summary = collab_service.get_collaboration_summary(ticket_id)
    return summary


# ============================================================================
# ANALYTICS & PREDICTIONS ENDPOINTS
# ============================================================================

@app.get("/api/v1/analytics/forecast", tags=["Analytics"])
async def get_volume_forecast(
    days_ahead: int = Query(7, alias="days"),
    db: Session = Depends(get_db)
):
    """Get ticket volume forecast"""
    ml_service = MLPredictionService(db)
    forecast = ml_service.forecast_ticket_volume(days_ahead)
    return forecast


@app.get("/api/v1/analytics/sla-prediction/{ticket_id}", tags=["Analytics"])
async def predict_sla_breach(ticket_id: int, db: Session = Depends(get_db)):
    """Predict SLA breach probability"""
    from app.models.ticket import TicketHistory
    ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

    if not ticket or not ticket.assigned_to:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned")

    ml_service = MLPredictionService(db)
    ticket_dict = {
        "priority": ticket.priority.value,
        "complexity": ticket.complexity.value if ticket.complexity else "moderate",
        "environment": ticket.environment
    }
    prediction = ml_service.predict_sla_breach_probability(ticket_dict, ticket.assigned_to)
    return prediction


@app.post("/api/v1/ml/train", tags=["Analytics"])
async def train_ml_models(force_retrain: bool = False, db: Session = Depends(get_db)):
    """
    Train ML models with historical data

    This endpoint trains:
    - Category classifier
    - Complexity predictor
    - Resolution time predictor

    Requires at least 100 resolved tickets in database.
    """
    ml_service = MLPredictionService(db)
    result = ml_service.train_models(force_retrain=force_retrain)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))

    return result


@app.get("/api/v1/analytics/team-performance", tags=["Analytics"])
async def get_team_performance(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get team performance metrics"""
    try:
        from app.models.performance import PerformanceMetric
        from app.models.team import TeamMember
        from datetime import datetime, timedelta

        # Default to last 30 days
        if not end_date:
            end_date = datetime.now().date()
        else:
            end_date = datetime.fromisoformat(end_date).date()

        if not start_date:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.fromisoformat(start_date).date()

        # Get performance metrics for the date range
        metrics = db.query(PerformanceMetric).filter(
            PerformanceMetric.date >= start_date,
            PerformanceMetric.date <= end_date
        ).all()

        # Aggregate by team member
        performance_data = {}
        for metric in metrics:
            member_id = metric.team_member_id
            if member_id not in performance_data:
                member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
                performance_data[member_id] = {
                    "member_id": member_id,
                    "member_name": member.name if member else "Unknown",
                    "team_level": member.team_level.value if member and hasattr(member.team_level, 'value') else str(member.team_level) if member else "L1",
                    "tickets_resolved": 0,  # Changed from total_resolved
                    "avg_resolution_time": 0,  # Changed from avg_resolution_time_hours
                    "sla_compliance_rate": 0
                }

            performance_data[member_id]["tickets_resolved"] += metric.tickets_resolved

        # Calculate averages
        for member_data in performance_data.values():
            if member_data["tickets_resolved"] > 0:
                # Get more detailed metrics from database
                member = db.query(TeamMember).filter(TeamMember.id == member_data["member_id"]).first()
                if member:
                    member_data["sla_compliance_rate"] = member.sla_compliance_rate
                    member_data["avg_resolution_time"] = member.avg_resolution_time_hours or 0

        return {
            "performance": list(performance_data.values()),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "total_members": len(performance_data)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch team performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ml/models/status", tags=["Analytics"])
async def get_ml_models_status():
    """Get status of ML models (loaded, last trained, etc.)"""
    import os
    from datetime import datetime

    models_path = settings.ML_MODELS_PATH
    models = [
        "category_classifier.joblib",
        "category_vectorizer.joblib",
        "complexity_classifier.joblib",
        "complexity_vectorizer.joblib",
        "resolution_regressor.joblib",
        "resolution_vectorizer.joblib"
    ]

    models_status = {}
    for model in models:
        path = f"{models_path}/{model}"
        if os.path.exists(path):
            mtime = os.path.getmtime(path)
            models_status[model] = {
                "exists": True,
                "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                "size_kb": round(os.path.getsize(path) / 1024, 2)
            }
        else:
            models_status[model] = {"exists": False}

    return {
        "models": models_status,
        "models_path": models_path,
        "all_present": all(m["exists"] for m in models_status.values())
    }


@app.post("/api/v1/ml/predict/category", tags=["Analytics"])
async def predict_ticket_category(
    subject: str,
    description: str = "",
    db: Session = Depends(get_db)
):
    """
    Predict ticket category using ML model

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)

    Returns:
        {
            "category": str,
            "confidence": float,
            "probabilities": Dict[str, float],
            "method": "ml" | "fallback"
        }
    """
    ml_service = MLPredictionService(db)
    ticket = {"subject": subject, "description": description}
    prediction = ml_service.predict_ticket_category(ticket)
    return prediction


@app.post("/api/v1/ml/predict/complexity", tags=["Analytics"])
async def predict_ticket_complexity(
    subject: str,
    description: str = "",
    priority: str = "P3(Medium)",
    db: Session = Depends(get_db)
):
    """
    Predict ticket complexity using ML model

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (for fallback)

    Returns:
        {
            "complexity": str,
            "confidence": float,
            "probabilities": Dict[str, float],
            "method": "ml" | "fallback"
        }
    """
    ml_service = MLPredictionService(db)
    ticket = {"subject": subject, "description": description, "priority": priority}
    prediction = ml_service.predict_ticket_complexity(ticket)
    return prediction


@app.post("/api/v1/ml/predict/resolution-time", tags=["Analytics"])
async def predict_resolution_time(
    subject: str,
    description: str = "",
    priority: str = "P3(Medium)",
    db: Session = Depends(get_db)
):
    """
    Predict resolution time using ML model

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (for fallback)

    Returns:
        {
            "estimated_hours": float,
            "confidence": float,
            "method": "ml" | "fallback"
        }
    """
    ml_service = MLPredictionService(db)
    ticket = {"subject": subject, "description": description, "priority": priority}
    prediction = ml_service.predict_resolution_time(ticket)
    return prediction


@app.post("/api/v1/ml/predict/all", tags=["Analytics"])
async def predict_all_ticket_attributes(
    subject: str,
    description: str = "",
    priority: str = "P3(Medium)",
    db: Session = Depends(get_db)
):
    """
    Get all ML predictions for a ticket in one call

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority

    Returns:
        {
            "category": {...},
            "complexity": {...},
            "resolution_time": {...}
        }
    """
    ml_service = MLPredictionService(db)
    ticket = {"subject": subject, "description": description, "priority": priority}

    category = ml_service.predict_ticket_category(ticket)
    complexity = ml_service.predict_ticket_complexity(ticket)
    resolution = ml_service.predict_resolution_time(ticket)

    return {
        "category": category,
        "complexity": complexity,
        "resolution_time": resolution,
        "ticket_summary": {
            "subject": subject,
            "predicted_category": category["category"],
            "predicted_complexity": complexity["complexity"],
            "predicted_hours": resolution["estimated_hours"],
            "avg_confidence": round((
                category.get("confidence", 0.5) +
                complexity.get("confidence", 0.5) +
                resolution.get("confidence", 0.5)
            ) / 3, 2)
        }
    }


# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/api/v1/dashboard/metrics", tags=["Dashboard"])
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Get comprehensive dashboard metrics

    Returns summary of:
    - Total tickets (by status)
    - SLA compliance rate
    - Team workload
    - Recent activity
    """
    try:
        from app.models.ticket import TicketHistory, TicketStatus, TicketPriority
        from app.models.team import TeamMember
        from sqlalchemy import func, and_, case, or_
        from datetime import timedelta

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        # Total tickets by status
        total_tickets = db.query(TicketHistory).count()
        open_tickets = db.query(TicketHistory).filter(
            TicketHistory.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        resolved_today = db.query(TicketHistory).filter(
            TicketHistory.resolved_at >= today_start
        ).count()

        # SLA metrics
        total_resolved = db.query(TicketHistory).filter(
            TicketHistory.resolved_at.isnot(None)
        ).count()
        sla_breached = db.query(TicketHistory).filter(
            TicketHistory.sla_breached == True
        ).count()
        sla_compliance_rate = ((total_resolved - sla_breached) / total_resolved * 100) if total_resolved > 0 else 100

        # Team metrics
        active_members = db.query(TeamMember).filter(TeamMember.active == True).count()

        # Avg resolution time (last 7 days)
        resolved_last_week = db.query(TicketHistory).filter(
            and_(
                TicketHistory.resolved_at >= week_ago,
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.created_at.isnot(None)
            )
        ).all()

        if resolved_last_week:
            resolution_times = [
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved_last_week
            ]
            avg_resolution_hours = sum(resolution_times) / len(resolution_times)
        else:
            avg_resolution_hours = 0

        # Count at-risk and critical tickets
        from app.models.sla import SLATracker, SLAStatus
        at_risk_count = db.query(SLATracker).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL])
        ).count()

        critical_count = db.query(TicketHistory).filter(
            TicketHistory.priority == TicketPriority.P1_CRITICAL,
            TicketHistory.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()

        # Calculate team capacity
        total_capacity = db.query(func.sum(TeamMember.max_tickets)).filter(
            TeamMember.active == True
        ).scalar() or 0

        team_capacity_percentage = round((open_tickets / total_capacity * 100) if total_capacity > 0 else 0, 1)

        # Count active collaborations
        from app.models.ticket import TicketCollaboration
        active_collaborations = db.query(func.count(func.distinct(TicketCollaboration.ticket_id))).scalar() or 0

        # Build 7-day window for trend insights
        day_windows = [today_start - timedelta(days=i) for i in range(6, -1, -1)]

        # Daily ticket creation trend (sparkline for Total Tickets)
        tickets_created_rows = (
            db.query(
                func.date_trunc('day', TicketHistory.created_at).label('day_bucket'),
                func.count(TicketHistory.id).label('count')
            )
            .filter(TicketHistory.created_at >= week_ago)
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        tickets_created_map = {
            (row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket): int(row.count)
            for row in tickets_created_rows
        }
        tickets_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": tickets_created_map.get(day.date(), 0)
            }
            for day in day_windows
        ]

        # SLA compliance trend (daily compliance rate)
        sla_trend_rows = (
            db.query(
                func.date_trunc('day', TicketHistory.resolved_at).label('day_bucket'),
                func.count(TicketHistory.id).label('resolved'),
                func.sum(
                    case((TicketHistory.sla_breached == False, 1), else_=0)
                ).label('within')
            )
            .filter(
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.resolved_at >= week_ago
            )
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        sla_trend_map = {}
        for row in sla_trend_rows:
            day_key = row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket
            resolved = int(row.resolved or 0)
            within = int(row.within or 0)
            rate = (within / resolved * 100) if resolved > 0 else 100.0
            sla_trend_map[day_key] = round(rate, 1)
        sla_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": sla_trend_map.get(day.date(), 100.0)
            }
            for day in day_windows
        ]

        # At risk / critical trend (daily snapshot of trackers that changed status)
        status_timestamp = func.coalesce(SLATracker.updated_at, SLATracker.created_at)
        at_risk_rows = (
            db.query(
                func.date_trunc('day', status_timestamp).label('day_bucket'),
                func.sum(case((SLATracker.status == SLAStatus.AT_RISK, 1), else_=0)).label('at_risk'),
                func.sum(case((SLATracker.status == SLAStatus.CRITICAL, 1), else_=0)).label('critical')
            )
            .filter(status_timestamp >= week_ago)
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        at_risk_map = {}
        for row in at_risk_rows:
            day_key = row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket
            at_risk_map[day_key] = int(row.at_risk or 0) + int(row.critical or 0)
        at_risk_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": at_risk_map.get(day.date(), 0)
            }
            for day in day_windows
        ]

        # Team capacity usage trend (open tickets vs capacity)
        open_statuses = [TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]
        capacity_sparkline = []
        for day_start in day_windows:
            day_end = day_start + timedelta(days=1)
            open_count = (
                db.query(func.count(TicketHistory.id))
                .filter(
                    TicketHistory.status.in_(open_statuses),
                    TicketHistory.created_at <= day_end,
                    or_(TicketHistory.resolved_at.is_(None), TicketHistory.resolved_at > day_start)
                )
                .scalar()
            ) or 0
            utilization = round((open_count / total_capacity * 100), 1) if total_capacity > 0 else 0
            capacity_sparkline.append(
                {
                    "label": day_start.strftime('%b %d'),
                    "value": utilization
                }
            )

        # Priority distribution for tickets created today
        priority_rows = (
            db.query(
                TicketHistory.priority,
                func.count(TicketHistory.id).label('count')
            )
            .filter(TicketHistory.created_at >= today_start)
            .group_by(TicketHistory.priority)
            .all()
        )
        priority_distribution = [
            {
                "label": priority.value if hasattr(priority, 'value') else str(priority),
                "value": int(row_count)
            }
            for priority, row_count in priority_rows
        ]

        # SLA status distribution for all trackers
        sla_distribution_rows = (
            db.query(
                SLATracker.status,
                func.count(SLATracker.id).label('count')
            )
            .group_by(SLATracker.status)
            .all()
        )
        sla_distribution = [
            {"label": status.value if hasattr(status, 'value') else str(status), "value": int(count)}
            for status, count in sla_distribution_rows
        ]

        # Capacity distribution across active team
        metrics_in_progress = open_tickets
        used_capacity = min(metrics_in_progress, total_capacity)
        remaining_capacity = max(total_capacity - used_capacity, 0)
        overflow_capacity = max(metrics_in_progress - total_capacity, 0)
        capacity_distribution = [
            {"label": "Active Load", "value": used_capacity}
        ]
        if remaining_capacity > 0:
            capacity_distribution.append({"label": "Available", "value": remaining_capacity})
        if overflow_capacity > 0:
            capacity_distribution.append({"label": "Overflow", "value": overflow_capacity})

        # At risk distribution (derived from SLA distribution)
        at_risk_distribution = []
        distribution_lookup = {item["label"]: item["value"] for item in sla_distribution}
        at_risk_distribution.append({"label": "At Risk", "value": distribution_lookup.get(SLAStatus.AT_RISK.value, 0)})
        at_risk_distribution.append({"label": "Critical", "value": distribution_lookup.get(SLAStatus.CRITICAL.value, 0)})
        safe_value = distribution_lookup.get(SLAStatus.WITHIN_SLA.value, 0)
        if safe_value:
            at_risk_distribution.append({"label": "Within SLA", "value": safe_value})

        card_insights = {
            "total_tickets": {
                "sparkline": tickets_sparkline,
                "distribution": priority_distribution,
            },
            "sla_compliance": {
                "sparkline": sla_sparkline,
                "distribution": sla_distribution,
            },
            "at_risk": {
                "sparkline": at_risk_sparkline,
                "distribution": at_risk_distribution,
            },
            "team_capacity": {
                "sparkline": capacity_sparkline,
                "distribution": capacity_distribution,
            },
        }

        return {
            "total_tickets_today": resolved_today,
            "tickets_in_progress": open_tickets,
            "sla_compliance_rate": round(sla_compliance_rate, 1),
            "avg_resolution_time_hours": round(avg_resolution_hours, 1),
            "at_risk_tickets": at_risk_count,
            "critical_tickets": critical_count,
            "team_capacity_percentage": team_capacity_percentage,
            "active_collaborations": active_collaborations,
            "card_insights": card_insights
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/dashboard/activity", tags=["Dashboard"])
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent ticket activity"""
    try:
        from app.models.ticket import TicketHistory

        tickets = db.query(TicketHistory).order_by(
            TicketHistory.updated_at.desc()
        ).limit(limit).all()

        return {
            "activities": [
                {
                    "ticket_id": t.id,
                    "redmine_ticket_id": t.redmine_ticket_id,
                    "subject": t.subject,
                    "status": t.status.value,
                    "assigned_to": t.assigned_to.name if t.assigned_to else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None
                }
                for t in tickets
            ]
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch recent activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SKILLS MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/team/skills", tags=["Team"])
async def get_skills(db: Session = Depends(get_db)):
    """Get all available skills"""
    try:
        from app.models.team import Skill

        skills = db.query(Skill).all()

        return {
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "category": s.category,
                    "description": s.description
                }
                for s in skills
            ],
            "total": len(skills)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/team/skills", tags=["Team"])
async def create_skill(
    name: str,
    category: str,
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new skill"""
    try:
        from app.models.team import Skill

        # Check if skill already exists
        existing = db.query(Skill).filter(Skill.name == name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Skill already exists")

        skill = Skill(
            name=name,
            category=category,
            description=description
        )

        db.add(skill)
        db.commit()
        db.refresh(skill)

        return {
            "success": True,
            "skill": {
                "id": skill.id,
                "name": skill.name,
                "category": skill.category,
                "description": skill.description
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REDMINE INTEGRATION ENDPOINTS
# ============================================================================

@app.get("/api/v1/redmine/group-members", tags=["Redmine"])
async def get_redmine_group_members(group_id: int = None):
    """
    Fetch all users from Redmine DevOps group

    This endpoint fetches users from the configured DevOps Team group in Redmine,
    including detailed information like email and login. Used for adding new team members.
    """
    try:
        redmine_service = RedmineService()
        members = redmine_service.get_group_members(group_id)

        return {
            "success": True,
            "count": len(members),
            "members": members
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch Redmine group members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/redmine/user/{user_id}", tags=["Redmine"])
async def get_redmine_user(user_id: int):
    """Get detailed information about a Redmine user"""
    try:
        redmine_service = RedmineService()
        user = redmine_service.get_user_details(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found in Redmine")

        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch Redmine user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/redmine/sync-statuses", tags=["Redmine"])
async def sync_redmine_statuses(db: Session = Depends(get_db)):
    """Synchronize ticket statuses with Redmine."""
    try:
        processor = TicketProcessor(db)
        result = processor.sync_ticket_statuses_with_redmine()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to sync Redmine statuses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TEAM MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/team/members", tags=["Team"])
async def get_team_members(
    team_level: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get all team members

    Args:
        team_level: Filter by team level (L1, L2, L3)
        active_only: Only return active members (default: True)
    """
    try:
        from app.models.team import TeamMember, TeamLevel
        from app.services.workload_manager import WorkloadManager

        query = db.query(TeamMember)

        if active_only:
            query = query.filter(TeamMember.active == True)

        if team_level:
            query = query.filter(TeamMember.team_level == TeamLevel(team_level))

        members = query.all()
        workload_manager = WorkloadManager(db)

        return {
            "success": True,
            "count": len(members),
            "members": [
                {
                    "id": m.id,
                    "redmine_user_id": m.redmine_user_id,
                    "user_id": m.user_id,
                    "name": m.name,
                    "email": m.email,
                    "team_level": m.team_level.value,
                    "max_tickets": m.max_tickets,
                    "current_tickets": workload_manager.get_current_workload(m.id),
                    "active": m.active,
                    "timezone": m.timezone,
                    "work_hours": f"{m.work_start_hour}:00 - {m.work_end_hour}:00",
                    "work_start_hour": m.work_start_hour,
                    "work_end_hour": m.work_end_hour,
                    "total_tickets_assigned": m.total_tickets_assigned,
                    "total_tickets_resolved": m.total_tickets_resolved,
                    "sla_compliance_rate": m.sla_compliance_rate,
                    "skills": [{"id": s.id, "name": s.name, "category": s.category} for s in m.skills]
                }
                for m in members
            ]
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/team/members/{member_id}", tags=["Team"])
async def get_team_member(member_id: int, db: Session = Depends(get_db)):
    """Get a single team member by ID"""
    try:
        from app.models.team import TeamMember

        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        return {
            "success": True,
            "member": {
                "id": member.id,
                "redmine_user_id": member.redmine_user_id,
                "user_id": member.user_id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets,
                "active": member.active,
                "timezone": member.timezone,
                "work_start_hour": member.work_start_hour,
                "work_end_hour": member.work_end_hour,
                "total_tickets_assigned": member.total_tickets_assigned,
                "total_tickets_resolved": member.total_tickets_resolved,
                "sla_compliance_rate": member.sla_compliance_rate,
                "skills": [{"id": s.id, "name": s.name, "category": s.category} for s in member.skills]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/team/members", tags=["Team"])
async def create_team_member(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Create a new team member by fetching details from Redmine

    Body:
    {
        "redmine_user_id": int,
        "team_level": "L1"|"L2"|"L3",
        "max_tickets": int (optional, default: 8),
        "timezone": str (optional, default: "Asia/Kolkata"),
        "work_start_hour": int (optional, default: 9),
        "work_end_hour": int (optional, default: 18)
    }
    """
    try:
        from app.models.team import TeamMember, TeamLevel

        # Extract parameters from JSON body
        redmine_user_id = data.get("redmine_user_id")
        team_level = data.get("team_level")
        max_tickets = data.get("max_tickets", 8)
        timezone = data.get("timezone", "Asia/Kolkata")
        work_start_hour = data.get("work_start_hour", 9)
        work_end_hour = data.get("work_end_hour", 18)
        skill_ids = data.get("skills", [])  # Array of skill IDs from frontend

        if not redmine_user_id:
            raise HTTPException(status_code=400, detail="redmine_user_id is required")
        if not team_level:
            raise HTTPException(status_code=400, detail="team_level is required")

        # Fetch user details from Redmine
        redmine_service = RedmineService()
        user_data = redmine_service.get_user_details(redmine_user_id)

        if not user_data:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {redmine_user_id} not found in Redmine"
            )

        if not user_data.get("email"):
            raise HTTPException(
                status_code=400,
                detail="Redmine user does not have a primary email address"
            )

        # Check if member already exists (Redmine ID or email) and reactivate if inactive
        existing = db.query(TeamMember).filter(
            TeamMember.redmine_user_id == redmine_user_id
        ).first()

        if not existing and user_data.get("email"):
            existing = db.query(TeamMember).filter(
                TeamMember.email == user_data["email"]
            ).first()

        if existing:
            if existing.active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Team member with Redmine ID {redmine_user_id} already exists"
                )

            existing.name = user_data['name']
            existing.email = user_data['email']
            existing.team_level = TeamLevel(team_level)
            existing.max_tickets = max_tickets
            existing.timezone = timezone
            existing.work_start_hour = work_start_hour
            existing.work_end_hour = work_end_hour
            existing.active = True

            # Update skills if provided
            if skill_ids:
                from app.models.team import Skill
                # Clear existing skills and add new ones
                existing.skills = []
                skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
                existing.skills = skills
                logger.debug(f"Associated {len(skills)} skills with team member {existing.id}")

            db.commit()
            db.refresh(existing)

            logger.info(f"✅ Reactivated team member: {existing.name} ({team_level})")

            return {
                "success": True,
                "message": f"Team member {existing.name} reactivated successfully",
                "member": {
                    "id": existing.id,
                    "redmine_user_id": existing.redmine_user_id,
                    "name": existing.name,
                    "email": existing.email,
                    "team_level": existing.team_level.value,
                    "max_tickets": existing.max_tickets
                }
            }

        # Create team member
        member = TeamMember(
            redmine_user_id=redmine_user_id,
            name=user_data['name'],
            email=user_data['email'],
            team_level=TeamLevel(team_level),
            max_tickets=max_tickets,
            timezone=timezone,
            work_start_hour=work_start_hour,
            work_end_hour=work_end_hour,
            active=True
        )

        db.add(member)
        db.flush()  # Flush to get member.id for relationship

        # Associate skills if provided
        if skill_ids:
            from app.models.team import Skill
            skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            member.skills = skills
            logger.debug(f"Associated {len(skills)} skills with new team member")

        db.commit()
        db.refresh(member)

        logger.info(f"✅ Created team member: {member.name} ({team_level})")

        return {
            "success": True,
            "message": f"Team member {member.name} created successfully",
            "member": {
                "id": member.id,
                "redmine_user_id": member.redmine_user_id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/team/members/{member_id}", tags=["Team"])
async def update_team_member(
    member_id: int,
    member_data: dict,
    db: Session = Depends(get_db)
):
    """Update team member details"""
    try:
        from app.models.team import TeamMember, TeamLevel

        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        logger.info(f"📝 Updating team member {member_id} ({member.name}). Data received: {member_data}")

        # Update fields
        if 'team_level' in member_data:
            old_level = member.team_level
            member.team_level = TeamLevel(member_data['team_level'])
            logger.info(f"  ↪️ Team level: {old_level} → {member.team_level}")
        if 'max_tickets' in member_data:
            member.max_tickets = member_data['max_tickets']
        if 'active' in member_data:
            member.active = member_data['active']
        if 'timezone' in member_data:
            member.timezone = member_data['timezone']
        if 'work_start_hour' in member_data:
            member.work_start_hour = member_data['work_start_hour']
        if 'work_end_hour' in member_data:
            member.work_end_hour = member_data['work_end_hour']

        # Update skills if provided
        if 'skills' in member_data:
            from app.models.team import Skill
            skill_ids = member_data['skills']
            # Clear existing skills and add new ones
            member.skills = []
            if skill_ids:
                skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
                member.skills = skills
                logger.debug(f"Updated {len(skills)} skills for team member {member_id}")

        db.commit()
        db.refresh(member)

        logger.info(f"✅ Updated team member: {member.name}")

        return {
            "success": True,
            "message": f"Team member {member.name} updated successfully",
            "member": {
                "id": member.id,
                "name": member.name,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets,
                "active": member.active
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/team/members/{member_id}", tags=["Team"])
async def delete_team_member(member_id: int, db: Session = Depends(get_db)):
    """Soft delete a team member (mark as inactive)"""
    try:
        from app.models.team import TeamMember

        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        # Soft delete - mark as inactive
        member.active = False
        db.commit()

        logger.info(f"✅ Deactivated team member: {member.name}")

        return {
            "success": True,
            "message": f"Team member {member.name} deactivated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/team/members/{member_id}/performance", tags=["Team"])
async def get_member_performance(
    member_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Get individual team member performance metrics
    Only accessible by ADMIN and SUPER_ADMIN roles
    """
    try:
        from app.models.team import TeamMember
        from app.models.ticket import TicketHistory, TicketStatus, TicketCollaboration
        from sqlalchemy import func, case
        from datetime import datetime, timedelta

        # User is already verified as ADMIN/SUPER_ADMIN by require_admin dependency
        if False:
            raise HTTPException(
                status_code=403,
                detail="Only administrators can view team member performance"
            )

        # Get team member
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        # Get all tickets assigned to this member
        tickets = db.query(TicketHistory).filter(
            TicketHistory.assigned_to_id == member_id
        ).all()

        # Calculate performance metrics
        total_tickets = len(tickets)
        tickets_open = sum(1 for t in tickets if t.status in [TicketStatus.NEW, TicketStatus.ASSIGNED])
        tickets_in_progress = sum(1 for t in tickets if t.status == TicketStatus.IN_PROGRESS)
        tickets_resolved = sum(1 for t in tickets if t.status == TicketStatus.RESOLVED)
        tickets_closed = sum(1 for t in tickets if t.status == TicketStatus.CLOSED)
        tickets_on_hold = sum(1 for t in tickets if t.status == TicketStatus.PENDING)

        # Calculate SLA compliance
        tickets_breached = sum(1 for t in tickets if t.sla_breached)
        sla_compliance_rate = ((total_tickets - tickets_breached) / total_tickets * 100) if total_tickets > 0 else 100.0

        # Calculate average resolution time (for resolved/closed tickets)
        resolution_times = []
        for ticket in tickets:
            if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                if ticket.closed_at and ticket.created_at:
                    resolution_time = (ticket.closed_at - ticket.created_at).total_seconds() / 3600  # hours
                    resolution_times.append(resolution_time)

        avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        # Current workload
        current_tickets = tickets_open + tickets_in_progress + tickets_on_hold
        max_tickets = member.max_tickets or 10
        capacity_percentage = (current_tickets / max_tickets * 100) if max_tickets > 0 else 0.0

        # Get recent tickets (last 10)
        recent_tickets = sorted(tickets, key=lambda t: t.updated_at or t.created_at, reverse=True)[:10]
        recent_tickets_data = []
        for ticket in recent_tickets:
            recent_tickets_data.append({
                "id": ticket.id,
                "redmine_ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "status": ticket.status.value,
                "priority": ticket.priority,
                "sla_breached": ticket.sla_breached,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
            })

        # Calculate workload trend (last 30 days)
        workload_trend = []
        now = datetime.utcnow()
        for i in range(30, 0, -1):
            date = now - timedelta(days=i)
            date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Count tickets that were active on this date
            active_count = 0
            for ticket in tickets:
                ticket_created = ticket.created_at.replace(tzinfo=None) if ticket.created_at else None
                ticket_closed = ticket.closed_at.replace(tzinfo=None) if ticket.closed_at else None

                if ticket_created and ticket_created <= date_end:
                    if not ticket_closed or ticket_closed >= date_start:
                        active_count += 1

            workload_trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "active_tickets": active_count
            })

        # Get collaboration stats
        collaborations = db.query(TicketCollaboration).filter(
            TicketCollaboration.team_member_id == member_id,
            TicketCollaboration.is_active == True
        ).count()

        return {
            "success": True,
            "member": {
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "active": member.active,
                "current_tickets": current_tickets,
                "max_tickets": max_tickets,
                "capacity_percentage": round(capacity_percentage, 2)
            },
            "performance": {
                "total_tickets_assigned": total_tickets,
                "tickets_open": tickets_open,
                "tickets_in_progress": tickets_in_progress,
                "tickets_resolved": tickets_resolved,
                "tickets_closed": tickets_closed,
                "tickets_on_hold": tickets_on_hold,
                "tickets_breached": tickets_breached,
                "sla_compliance_rate": round(sla_compliance_rate, 2),
                "avg_resolution_time_hours": round(avg_resolution_time, 2),
                "active_collaborations": collaborations
            },
            "recent_tickets": recent_tickets_data,
            "workload_trend": workload_trend
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get member performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SCHEDULER STATUS ENDPOINT
# ============================================================================

@app.get("/api/v1/scheduler/status", tags=["Scheduler"])
async def get_scheduler_status():
    """Get status of background scheduler jobs"""
    try:
        from app.scheduler.scheduler import scheduler

        if not scheduler:
            return {
                "running": False,
                "jobs": [],
                "message": "Scheduler not initialized"
            }

        jobs = []
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "running": scheduler.running,
            "jobs": jobs,
            "total_jobs": len(jobs)
        }

    except Exception as e:
        logger.error(f"❌ Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ACTIVITY FEED ENDPOINTS
# ============================================================================

@app.get("/api/v1/activities", tags=["Activities"])
async def get_activities(
    limit: int = 50,
    hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Get recent activities for real-time feed

    Args:
        limit: Maximum number of activities (default: 50)
        hours: Get activities from last N hours (default: 24)

    Returns:
        List of recent activities
    """
    try:
        from app.services.activity_tracker import ActivityTracker

        tracker = ActivityTracker(db)
        activities = tracker.get_recent_activities(limit=limit, hours=hours)

        return {
            "success": True,
            "count": len(activities),
            "activities": [activity.to_dict() for activity in activities]
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/activities/ticket/{ticket_id}", tags=["Activities"])
async def get_ticket_activities(
    ticket_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get activities for a specific ticket"""
    try:
        from app.services.activity_tracker import ActivityTracker

        tracker = ActivityTracker(db)
        activities = tracker.get_ticket_activities(ticket_id, limit=limit)

        return {
            "success": True,
            "ticket_id": ticket_id,
            "count": len(activities),
            "activities": [activity.to_dict() for activity in activities]
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch ticket activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}

    async def connect(self, websocket: WebSocket, ticket_id: str):
        await websocket.accept()
        if ticket_id not in self.active_connections:
            self.active_connections[ticket_id] = []
        self.active_connections[ticket_id].append(websocket)
        logger.info(f"WebSocket connected for ticket {ticket_id}")

    def disconnect(self, websocket: WebSocket, ticket_id: str):
        if ticket_id in self.active_connections:
            self.active_connections[ticket_id].remove(websocket)
        logger.info(f"WebSocket disconnected for ticket {ticket_id}")

    async def broadcast(self, ticket_id: str, message: dict):
        if ticket_id in self.active_connections:
            for connection in self.active_connections[ticket_id]:
                await connection.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/ticket/{ticket_id}")
async def websocket_ticket(websocket: WebSocket, ticket_id: str):
    """WebSocket for real-time ticket updates"""
    await manager.connect(websocket, ticket_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast to all connected clients for this ticket
            await manager.broadcast(ticket_id, {"message": data, "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        manager.disconnect(websocket, ticket_id)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"💥 Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
