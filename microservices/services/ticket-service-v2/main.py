#!/usr/bin/env python3
"""
Ticket Service - Production Microservice
Extracted from monolithic main.py (lines 252-1208)

This service handles:
- Ticket listing with advanced filtering
- Ticket CRUD operations
- Ticket comments
- Ticket processing pipeline
- Resolution tracking
"""

import sys
import os

# Add backend to path to reuse existing services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../backend'))

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from loguru import logger

# Import from existing backend (reuse!)
from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_current_user, get_current_user_optional, require_admin
from app.models.ticket import TicketHistory, TicketStatus, TicketPriority, TicketCategory, ComplexityLevel, TicketComment, TicketCollaboration
from app.models.team import TeamMember, TeamLevel
from app.models.user import User, UserRole
from app.models.sla import SLATracker, SLAStatus
from app.models.filter import SavedTicketFilter
from app.models.work_session import WorkSession, SessionType

# Import existing services (reuse business logic!)
from app.services.ticket_processor import TicketProcessor
from app.services.redmine_service import RedmineService
from app.services.work_session_service import WorkSessionService

# Initialize FastAPI app
app = FastAPI(
    title="Ticket Service",
    version="2.0.0",
    description="Ticket management microservice - handles all ticket operations"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class TicketResolutionRequest(BaseModel):
    """Request payload for resolving a ticket"""
    resolution_notes: str = Field(..., min_length=3, max_length=5000)
    close_ticket: bool = Field(default=False)


class CommentCreate(BaseModel):
    """Create comment request"""
    content: str = Field(..., min_length=1)
    is_internal: bool = Field(default=False)


class CommentUpdate(BaseModel):
    """Update comment request"""
    content: str = Field(..., min_length=1)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "ticket-service",
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# GET /api/v1/tickets - List Tickets (EXACT COPY from main.py line 252)
# ============================================================================

@app.get("/api/v1/tickets")
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

    EXACT IMPLEMENTATION from main.py (lines 252-728)
    """
    try:
        query_params = request.query_params

        def normalize_priority(value: str) -> Optional[TicketPriority]:
            if not value:
                return None
            normalized = value.strip()
            alias = {
                "P1": "P1(Critical)", "P1CRITICAL": "P1(Critical)",
                "P2": "P2(High)", "P2HIGH": "P2(High)",
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

        # Build filters (same logic as main.py)
        filters_payload = {
            "statuses": [status] if status else [],
            "priorities": [priority] if priority else [],
            "team_levels": [team_level] if team_level else [],
            "sla_statuses": [sla_status] if sla_status else [],
            "assigned_to_ids": [assigned_to_id] if assigned_to_id else [],
            "categories": [],
            "created_from": created_from,
            "created_to": created_to,
            "ticket_number": ticket_number,
        }

        # Parse query params
        filters_payload["statuses"].extend(query_params.getlist("status"))
        filters_payload["priorities"].extend(query_params.getlist("priority"))
        filters_payload["team_levels"].extend(query_params.getlist("team_level"))
        filters_payload["sla_statuses"].extend(query_params.getlist("sla_status"))
        filters_payload["assigned_to_ids"].extend([int(v) for v in query_params.getlist("assigned_to_id") if v.isdigit()])
        filters_payload["categories"].extend(query_params.getlist("category"))

        # Apply saved filter if provided
        saved_filters_applied = None
        if filter_id:
            saved_filter = db.query(SavedTicketFilter).filter(SavedTicketFilter.id == filter_id).first()
            if not saved_filter:
                raise HTTPException(status_code=404, detail="Saved filter not found")
            saved_filters_applied = {
                "id": saved_filter.id,
                "name": saved_filter.name,
                "description": saved_filter.description,
            }
            payload = saved_filter.filters or {}
            filters_payload["statuses"].extend(payload.get("statuses", []))
            filters_payload["priorities"].extend(payload.get("priorities", []))
            filters_payload["team_levels"].extend(payload.get("team_levels", []))

        # Build query filters
        filters = []
        need_sla_join = False

        if filters_payload["statuses"]:
            status_filters = []
            for s in filters_payload["statuses"]:
                try:
                    status_filters.append(TicketStatus(s))
                except ValueError:
                    pass
            if status_filters:
                filters.append(TicketHistory.status.in_(status_filters))

        if filters_payload["priorities"]:
            priority_filters = []
            for p in filters_payload["priorities"]:
                normalized = normalize_priority(p)
                if normalized:
                    priority_filters.append(normalized)
            if priority_filters:
                filters.append(TicketHistory.priority.in_(priority_filters))

        if filters_payload["team_levels"]:
            team_levels = [l for l in filters_payload["team_levels"] if l in {"L1", "L2", "L3"}]
            if team_levels:
                filters.append(TicketHistory.team_level.in_(team_levels))

        if filters_payload["assigned_to_ids"]:
            filters.append(TicketHistory.assigned_to_id.in_(filters_payload["assigned_to_ids"]))

        created_from_dt = parse_datetime(filters_payload.get("created_from"))
        created_to_dt = parse_datetime(filters_payload.get("created_to"))

        if created_from_dt:
            filters.append(TicketHistory.created_at >= created_from_dt)
        if created_to_dt:
            filters.append(TicketHistory.created_at <= created_to_dt)

        if filters_payload.get("ticket_number"):
            try:
                ticket_num = int(str(filters_payload["ticket_number"]).strip())
                filters.append(TicketHistory.redmine_ticket_id == ticket_num)
            except (ValueError, TypeError):
                pass

        # SLA filters
        if filters_payload["sla_statuses"]:
            need_sla_join = True
            sla_conditions = []
            for sla_val in filters_payload["sla_statuses"]:
                if sla_val == "breached":
                    sla_conditions.append(TicketHistory.sla_breached == True)
                elif sla_val == "at_risk":
                    sla_conditions.append(SLATracker.status == SLAStatus.AT_RISK)
            if sla_conditions:
                filters.append(or_(*sla_conditions))

        # Build query
        base_query = db.query(TicketHistory)
        if need_sla_join:
            base_query = base_query.join(SLATracker, SLATracker.ticket_id == TicketHistory.id, isouter=True)

        # RBAC for VIEWER role
        if current_user and current_user.role == UserRole.VIEWER:
            team_member = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).first()
            if team_member:
                viewer_filter = or_(
                    TicketHistory.assigned_to_id == team_member.id,
                    TicketHistory.id.in_(
                        db.query(TicketCollaboration.ticket_id)
                        .filter(TicketCollaboration.team_member_id == team_member.id)
                        .filter(TicketCollaboration.is_active == True)
                    )
                )
                filters.append(viewer_filter)
            else:
                filters.append(TicketHistory.id == -1)

        filtered_query = base_query.filter(*filters)
        total = filtered_query.count()
        tickets = filtered_query.order_by(TicketHistory.created_at.desc()).offset(offset).limit(limit).all()

        # Fetch SLA trackers
        ticket_ids = [t.id for t in tickets]
        sla_trackers = db.query(SLATracker).filter(SLATracker.ticket_id.in_(ticket_ids)).all() if ticket_ids else []
        sla_by_ticket = {sla.ticket_id: sla for sla in sla_trackers}

        # Fetch active work sessions
        active_sessions = db.query(WorkSession).filter(
            WorkSession.ticket_id.in_(ticket_ids),
            WorkSession.is_active == True
        ).all() if ticket_ids else []
        active_session_by_ticket = {s.ticket_id: s for s in active_sessions}

        # Helper function
        def _enum_value(value):
            return value.value if hasattr(value, "value") else value

        # Build response
        return {
            "tickets": [
                {
                    "id": t.id,
                    "redmine_ticket_id": t.redmine_ticket_id,
                    "subject": t.subject,
                    "description": t.description,
                    "priority": _enum_value(t.priority),
                    "status": _enum_value(t.status),
                    "requester_name": t.requester_name,
                    "sla_tracker": {
                        "id": sla_by_ticket[t.id].id,
                        "status": _enum_value(sla_by_ticket[t.id].status),
                        "time_remaining_minutes": sla_by_ticket[t.id].calculate_time_remaining("resolution"),
                        "paused": sla_by_ticket[t.id].paused,
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
                    "total_work_minutes": int(t.total_work_minutes or 0),
                    "resolution_notes": t.resolution_notes,
                    "active_session": {
                        "id": active_session.id,
                        "type": _enum_value(active_session.session_type),
                        "started_at": active_session.started_at.isoformat()
                    } if (active_session := active_session_by_ticket.get(t.id)) else None
                }
                for t in tickets
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
            "saved_filter": saved_filters_applied
        }

    except Exception as e:
        logger.exception("❌ Failed to fetch tickets")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POST /api/v1/tickets/process - Process New Tickets (line 730)
# ============================================================================

@app.post("/api/v1/tickets/process")
async def process_tickets(db: Session = Depends(get_db)):
    """
    Process all new tickets through the pipeline
    Uses existing TicketProcessor service
    """
    try:
        processor = TicketProcessor(db)
        result = processor.process_new_tickets()
        return result
    except Exception as e:
        logger.error(f"❌ Process tickets failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POST /api/v1/tickets/{ticket_id}/resolve - Resolve Ticket (line 769)
# ============================================================================

@app.post("/api/v1/tickets/{ticket_id}/resolve")
async def resolve_ticket(
    ticket_id: int,
    resolution_data: TicketResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolve a ticket with notes"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Update ticket
        ticket.status = TicketStatus.CLOSED if resolution_data.close_ticket else TicketStatus.RESOLVED
        ticket.resolved_at = datetime.now()
        ticket.resolution_notes = resolution_data.resolution_notes

        # Update in Redmine
        redmine_service = RedmineService()
        status_id = 5 if resolution_data.close_ticket else 3
        redmine_service.update_issue(
            ticket.redmine_ticket_id,
            status_id=status_id,
            notes=f"Resolved by {current_user.username}: {resolution_data.resolution_notes}"
        )

        db.commit()
        db.refresh(ticket)

        logger.info(f"✅ Ticket #{ticket.redmine_ticket_id} resolved by {current_user.username}")

        return {
            "success": True,
            "ticket_id": ticket.id,
            "redmine_ticket_id": ticket.redmine_ticket_id,
            "status": ticket.status.value,
            "resolved_at": ticket.resolved_at.isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to resolve ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GET /api/v1/tickets/{ticket_id} - Get Single Ticket (line 882)
# ============================================================================

@app.get("/api/v1/tickets/{ticket_id}")
async def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get a single ticket by ID"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Check permissions
        if current_user and current_user.role == UserRole.VIEWER:
            team_member = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).first()
            if team_member:
                is_assigned = ticket.assigned_to_id == team_member.id
                is_collaborating = db.query(TicketCollaboration).filter(
                    TicketCollaboration.ticket_id == ticket.id,
                    TicketCollaboration.team_member_id == team_member.id,
                    TicketCollaboration.is_active == True
                ).first()

                if not (is_assigned or is_collaborating):
                    raise HTTPException(status_code=403, detail="Access denied")

        # Fetch related data
        sla_tracker = db.query(SLATracker).filter(SLATracker.ticket_id == ticket.id).first()
        comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket.id).order_by(TicketComment.created_at).all()

        def _enum_value(value):
            return value.value if hasattr(value, "value") else value

        return {
            "id": ticket.id,
            "redmine_ticket_id": ticket.redmine_ticket_id,
            "subject": ticket.subject,
            "description": ticket.description,
            "priority": _enum_value(ticket.priority),
            "status": _enum_value(ticket.status),
            "category": _enum_value(ticket.category) if ticket.category else None,
            "complexity": _enum_value(ticket.complexity) if ticket.complexity else None,
            "assigned_to": {
                "id": ticket.assigned_to.id,
                "name": ticket.assigned_to.name
            } if ticket.assigned_to else None,
            "sla_tracker": {
                "status": _enum_value(sla_tracker.status),
                "time_remaining_minutes": sla_tracker.calculate_time_remaining("resolution"),
            } if sla_tracker else None,
            "comments": [
                {
                    "id": c.id,
                    "content": c.content,
                    "created_by": c.created_by.username if c.created_by else None,
                    "created_at": c.created_at.isoformat()
                }
                for c in comments
            ],
            "created_at": ticket.created_at.isoformat(),
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# PUT /api/v1/tickets/{ticket_id} - Update Ticket (line 922)
# ============================================================================

@app.put("/api/v1/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: int,
    update_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a ticket"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

        # Update allowed fields
        if "status" in update_data:
            try:
                ticket.status = TicketStatus(update_data["status"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")

        if "priority" in update_data:
            try:
                ticket.priority = TicketPriority(update_data["priority"])
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid priority")

        if "assigned_to_id" in update_data:
            ticket.assigned_to_id = update_data["assigned_to_id"]

        db.commit()
        db.refresh(ticket)

        logger.info(f"✅ Ticket #{ticket.redmine_ticket_id} updated by {current_user.username}")

        return {
            "success": True,
            "ticket_id": ticket.id,
            "redmine_ticket_id": ticket.redmine_ticket_id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Continued in next message due to length...


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Ticket Service v2.0.0")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Shutting down Ticket Service...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
