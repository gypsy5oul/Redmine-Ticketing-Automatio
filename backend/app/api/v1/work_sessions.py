#!/usr/bin/env python3
"""
Work Session API - Start/Pause/Resume time tracking for tickets.
"""

from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError

from app.api.deps import get_current_user, get_db
from app.models.ticket import TicketHistory
from app.models.team import TeamMember
from app.models.user import User, UserRole
from app.models.work_session import SessionType
from app.services.work_session_service import WorkSessionService, WAITING_SESSION_TYPES

router = APIRouter(prefix="/api/v1", tags=["Work Sessions"])


class PauseWorkRequest(BaseModel):
    reason: SessionType = Field(..., description="Waiting reason (waiting_customer, waiting_approval, etc.)")
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional context about why the session is paused",
    )

    @validator("reason")
    def validate_reason(cls, value: SessionType) -> SessionType:
        if value not in WAITING_SESSION_TYPES:
            raise ValueError("Reason must be one of the waiting_* categories")
        return value


class WorkActionResponse(BaseModel):
    success: bool
    ticket_id: int
    session_id: int
    ticket_status: str
    active_sessions_count: int
    can_accept_more_work: bool
    started_at: Optional[str] = None


def _session_type_to_str(value: Union[str, SessionType, None]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, SessionType):
        return value.value
    if isinstance(value, str):
        try:
            return SessionType(value).value
        except ValueError:
            return value
    return str(value)


def _get_team_member_for_user(db: Session, user: User) -> TeamMember:
    member = db.query(TeamMember).filter(TeamMember.user_id == user.id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not linked to an engineering team member",
        )
    return member


def _get_ticket(db: Session, ticket_id: int) -> TicketHistory:
    ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _ensure_ticket_access(ticket: TicketHistory, user: User, member: Optional[TeamMember]) -> None:
    """
    Ensure the caller has rights to operate on this ticket.

    Engineers can only interact with tickets assigned to them.
    Admin/super-admin users are permitted to view summaries but still require
    a member mapping to perform actions.
    """
    privileged = user.role in {UserRole.ADMIN, UserRole.SUPER_ADMIN}
    if ticket.assigned_to_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket is currently unassigned. Assign it before tracking work.",
        )
    if member and ticket.assigned_to_id == member.id:
        return
    if privileged:
        # Allow admin users with explicit team-member mapping to act on behalf.
        if member and member.id == ticket.assigned_to_id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin users must impersonate an assigned engineer to control work sessions.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Ticket is not assigned to the current engineer.",
    )


@router.post(
    "/tickets/{ticket_id}/work/start",
    response_model=WorkActionResponse,
    summary="Start active work on a ticket",
)
def start_work_session(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = WorkSessionService(db)
    ticket = _get_ticket(db, ticket_id)
    member = _get_team_member_for_user(db, current_user)
    _ensure_ticket_access(ticket, current_user, member)

    try:
        session, status_payload = service.start_work_session(ticket_id, member.id)
        response_payload = dict(status_payload)
        response_payload["session_id"] = session.id
        return WorkActionResponse(**response_payload)
    except ValueError as exc:
        logger.warning("Failed to start work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (IntegrityError, DatabaseError) as exc:
        logger.error("Database error starting work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while starting work session"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error starting work session for ticket %s", ticket_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        ) from exc


@router.post(
    "/tickets/{ticket_id}/work/pause",
    summary="Pause active work and enter a waiting state",
)
def pause_work_session(
    ticket_id: int,
    payload: PauseWorkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = WorkSessionService(db)
    ticket = _get_ticket(db, ticket_id)
    member = _get_team_member_for_user(db, current_user)
    _ensure_ticket_access(ticket, current_user, member)

    try:
        active_session, waiting_session = service.pause_work_session(
            ticket_id=ticket_id,
            member_id=member.id,
            reason=payload.reason.value,
            notes=payload.notes,
        )
        return {
            "ended_session": {
                "id": active_session.id,
                "type": _session_type_to_str(active_session.session_type),
                "duration_minutes": active_session.duration_minutes,
            },
            "waiting_session": {
                "id": waiting_session.id,
                "type": _session_type_to_str(waiting_session.session_type),
                "started_at": waiting_session.started_at.isoformat() if waiting_session.started_at else None,
            },
            "ticket_id": ticket_id,
        }
    except ValueError as exc:
        logger.warning("Failed to pause work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (IntegrityError, DatabaseError) as exc:
        logger.error("Database error pausing work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while pausing work session"
        ) from exc


@router.post(
    "/tickets/{ticket_id}/work/resume",
    summary="Resume active work on a ticket",
)
def resume_work_session(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = WorkSessionService(db)
    ticket = _get_ticket(db, ticket_id)
    member = _get_team_member_for_user(db, current_user)
    _ensure_ticket_access(ticket, current_user, member)

    try:
        waiting_session, new_session = service.resume_work_session(ticket_id, member.id)
        return {
            "ended_waiting_session": {
                "id": waiting_session.id,
                "type": _session_type_to_str(waiting_session.session_type),
                "duration_minutes": waiting_session.duration_minutes,
            },
            "active_session": {
                "id": new_session.id,
                "started_at": new_session.started_at.isoformat() if new_session.started_at else None,
                "type": _session_type_to_str(new_session.session_type),
            },
            "ticket_id": ticket_id,
        }
    except ValueError as exc:
        logger.warning("Failed to resume work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (IntegrityError, DatabaseError) as exc:
        logger.error("Database error resuming work session for ticket %s: %s", ticket_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while resuming work session"
        ) from exc


@router.get(
    "/tickets/{ticket_id}/work/summary",
    summary="Get complete work-session summary for a ticket",
)
def get_work_summary(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = WorkSessionService(db)
    ticket = _get_ticket(db, ticket_id)

    # Allow admins/super-admins to view, otherwise ensure engineer mapping.
    member: Optional[TeamMember] = None
    if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
        member = _get_team_member_for_user(db, current_user)
        _ensure_ticket_access(ticket, current_user, member)

    try:
        return service.get_work_summary(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/work/active",
    summary="Get the caller's active work sessions",
)
def get_active_sessions_for_member(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        member = _get_team_member_for_user(db, current_user)
    except HTTPException:
        # Non-engineer users simply receive an empty list.
        return {"active_sessions": []}

    service = WorkSessionService(db)
    sessions = service.get_member_active_sessions(member.id)
    return {
        "active_sessions": sessions,
        "member_id": member.id,
    }
