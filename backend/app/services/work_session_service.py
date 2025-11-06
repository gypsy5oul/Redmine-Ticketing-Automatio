#!/usr/bin/env python3
"""
Work Session Service - Accurate time tracking for tickets

Responsibilities
----------------
- Manage active work, waiting, and idle sessions for tickets.
- Enforce concurrent work-session limits per engineer.
- Track engineer capacity and idle time when tickets are not picked up.
- Provide aggregated summaries for tickets and engineers.
"""

from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.orm import Session

from app.models.ticket import TicketHistory, TicketStatus
from app.models.work_session import EngineerWorkStatus, SessionType, WorkSession

WAITING_SESSION_TYPES = {
    SessionType.WAITING_CUSTOMER,
    SessionType.WAITING_APPROVAL,
    SessionType.WAITING_DEPLOYMENT,
    SessionType.WAITING_EXTERNAL,
}


def _enum_value(value):
    """Return enum value if available, otherwise the original object."""
    return value.value if hasattr(value, "value") else value


class WorkSessionService:
    """Manage work sessions and engineer capacity tracking."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Public API - Session lifecycle
    # ------------------------------------------------------------------ #
    def start_work_session(self, ticket_id: int, member_id: int) -> Tuple[WorkSession, Dict]:
        """
        Start a new active work session.

        Raises:
            ValueError: If ticket not found, not assigned to member, or concurrent limit reached.
        """
        now = datetime.now(tz.utc)

        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        if ticket.assigned_to_id != member_id:
            raise ValueError(f"Ticket {ticket_id} is not assigned to member {member_id}")

        work_status = self._get_or_create_work_status(member_id)
        if work_status.active_work_sessions_count >= work_status.max_concurrent_sessions:
            raise ValueError(
                "Active work-session limit reached. Pause another ticket before starting new work."
            )

        # Ensure any idle tracking is closed before starting active work
        self._end_idle_session(ticket_id, now)

        session_number = self._get_next_session_number(ticket_id)
        work_session = WorkSession(
            ticket_id=ticket_id,
            team_member_id=member_id,
            session_type=SessionType.ACTIVE_WORK,
            is_active=True,
            session_number=session_number,
            started_at=now,
        )
        self.db.add(work_session)
        self.db.flush()  # Assign session ID

        ticket.status = TicketStatus.IN_PROGRESS
        ticket.work_started_at = ticket.work_started_at or now
        ticket.last_work_session_at = now
        ticket.active_work_session_id = work_session.id

        # Update engineer status
        work_status.active_work_sessions_count += 1
        work_status.is_idle = False
        work_status.idle_since = None
        work_status.last_activity_at = now
        work_status.can_accept_work = (
            work_status.active_work_sessions_count < work_status.max_concurrent_sessions
        )

        self.db.commit()
        self.db.refresh(work_session)
        self._recompute_engineer_state(member_id, reference_time=now)

        logger.info(
            "✅ Started work session %s for ticket %s by member %s",
            work_session.id,
            ticket_id,
            member_id,
        )

        return work_session, {
            "success": True,
            "ticket_id": ticket_id,
            "session_id": work_session.id,
            "ticket_status": _enum_value(ticket.status),
            "active_sessions_count": work_status.active_work_sessions_count,
            "can_accept_more_work": work_status.can_accept_work,
            "started_at": work_session.started_at.isoformat(),
        }

    def pause_work_session(
        self,
        ticket_id: int,
        member_id: int,
        reason: str,
        notes: Optional[str] = None,
    ) -> Tuple[WorkSession, WorkSession]:
        """
        Pause the active work session and start a waiting-period session.

        Args:
            reason: Must map to one of the waiting SessionType values.
        """
        now = datetime.now(tz.utc)
        waiting_type = self._map_waiting_reason(reason)

        active_session = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.ticket_id == ticket_id,
                WorkSession.team_member_id == member_id,
                WorkSession.is_active.is_(True),
                WorkSession.session_type == SessionType.ACTIVE_WORK,
            )
            .first()
        )

        if not active_session:
            raise ValueError(f"No active work session found for ticket {ticket_id}")

        self._finalize_session(active_session, now)

        waiting_session = WorkSession(
            ticket_id=ticket_id,
            team_member_id=member_id,
            session_type=waiting_type,
            is_active=True,
            session_number=active_session.session_number + 1,
            started_at=now,
            paused_reason=notes or _enum_value(waiting_type),
        )
        self.db.add(waiting_session)
        self.db.flush()

        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if ticket:
            ticket.status = TicketStatus.PENDING
            ticket.active_work_session_id = None
            ticket.last_work_session_at = now

        self.db.commit()
        self.db.refresh(waiting_session)
        self._recompute_engineer_state(member_id, reference_time=now)

        logger.info(
            "⏸ Paused work session %s and created waiting session %s for ticket %s",
            active_session.id,
            waiting_session.id,
            ticket_id,
        )
        return active_session, waiting_session

    def resume_work_session(self, ticket_id: int, member_id: int) -> Tuple[WorkSession, WorkSession]:
        """
        Resume work from an active waiting session.
        """
        now = datetime.now(tz.utc)

        waiting_session = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.ticket_id == ticket_id,
                WorkSession.team_member_id == member_id,
                WorkSession.is_active.is_(True),
                WorkSession.session_type != SessionType.ACTIVE_WORK,
            )
            .first()
        )

        if not waiting_session:
            raise ValueError(f"No active waiting session found for ticket {ticket_id}")

        self._finalize_session(waiting_session, now)

        session_number = waiting_session.session_number + 1
        new_session = WorkSession(
            ticket_id=ticket_id,
            team_member_id=member_id,
            session_type=SessionType.ACTIVE_WORK,
            is_active=True,
            session_number=session_number,
            started_at=now,
        )
        self.db.add(new_session)
        self.db.flush()

        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if ticket:
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.active_work_session_id = new_session.id
            ticket.last_work_session_at = now

        self.db.commit()
        self.db.refresh(new_session)
        self._recompute_engineer_state(member_id, reference_time=now)

        logger.info(
            "▶️ Resumed work on ticket %s (session %s), after waiting session %s",
            ticket_id,
            new_session.id,
            waiting_session.id,
        )
        return waiting_session, new_session

    def end_work_session(
        self,
        ticket_id: int,
        member_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Dict:
        """
        End all active sessions for a ticket (used when resolving/closing).
        """
        now = datetime.now(tz.utc)
        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        self._finalize_all_active_sessions(ticket_id, end_time=now)

        if notes:
            # Attach notes to the last active session if available
            last_session = (
                self.db.query(WorkSession)
                .filter(WorkSession.ticket_id == ticket_id)
                .order_by(WorkSession.id.desc())
                .first()
            )
            if last_session and not last_session.notes:
                last_session.notes = notes

        self.db.commit()

        target_member_id = member_id or ticket.assigned_to_id
        if target_member_id:
            self._recompute_engineer_state(target_member_id, reference_time=now)

        logger.info("✅ Ended all work sessions for ticket %s", ticket_id)
        return self.get_work_summary(ticket_id)

    # ------------------------------------------------------------------ #
    # Assignment & idle management
    # ------------------------------------------------------------------ #
    def ensure_idle_session(
        self,
        ticket_id: int,
        member_id: int,
        started_at: Optional[datetime] = None,
        commit: bool = True,
    ) -> Optional[WorkSession]:
        """
        Start an idle session if the ticket has no active sessions.
        """
        now = started_at or datetime.now(tz.utc)
        has_active = (
            self.db.query(WorkSession)
            .filter(WorkSession.ticket_id == ticket_id, WorkSession.is_active.is_(True))
            .first()
        )

        if has_active:
            return None

        session_number = self._get_next_session_number(ticket_id)
        idle_session = WorkSession(
            ticket_id=ticket_id,
            team_member_id=member_id,
            session_type=SessionType.IDLE,
            is_active=True,
            session_number=session_number,
            started_at=now,
            paused_reason="Ticket assigned but work not yet started",
        )
        self.db.add(idle_session)
        self.db.flush()

        work_status = self._get_or_create_work_status(member_id)
        work_status.is_idle = True
        work_status.idle_since = now if not work_status.idle_since else work_status.idle_since
        work_status.last_activity_at = now

        if commit:
            self.db.commit()
            self.db.refresh(idle_session)
        else:
            self.db.flush()

        self._recompute_engineer_state(member_id, reference_time=now, force_idle=True)

        logger.debug(
            "🚦 Started idle tracking session %s for ticket %s (member %s)",
            idle_session.id,
            ticket_id,
            member_id,
        )
        return idle_session

    def handle_assignment_change(
        self,
        ticket: TicketHistory,
        new_member_id: int,
        previous_member_id: Optional[int] = None,
    ) -> None:
        """
        Finalize sessions for previous assignee and begin idle tracking for the new assignee.
        """
        now = datetime.now(tz.utc)
        self._finalize_all_active_sessions(ticket.id, end_time=now)

        if previous_member_id and previous_member_id != new_member_id:
            self._recompute_engineer_state(previous_member_id, reference_time=now)

        self.ensure_idle_session(ticket.id, new_member_id, started_at=now, commit=False)
        self._recompute_engineer_state(new_member_id, reference_time=now, force_idle=True)

        self.db.commit()
        logger.info(
            "👥 Updated assignment for ticket %s → member %s (previous %s)",
            ticket.id,
            new_member_id,
            previous_member_id,
        )

    # ------------------------------------------------------------------ #
    # Queries & summaries
    # ------------------------------------------------------------------ #
    def get_active_session(self, ticket_id: int) -> Optional[WorkSession]:
        """Return the currently active session for a ticket, if any."""
        return (
            self.db.query(WorkSession)
            .filter(WorkSession.ticket_id == ticket_id, WorkSession.is_active.is_(True))
            .order_by(WorkSession.started_at.asc())
            .first()
        )

    def get_member_active_sessions(self, member_id: int) -> List[Dict]:
        """Return all active work sessions for a specific engineer."""
        sessions = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.team_member_id == member_id,
                WorkSession.is_active.is_(True),
                WorkSession.session_type == SessionType.ACTIVE_WORK,
            )
            .all()
        )

        now = datetime.now(tz.utc)
        result: List[Dict] = []
        for session in sessions:
            ticket = session.ticket
            duration_minutes = int((now - session.started_at).total_seconds() / 60)
            result.append(
                {
                    "session_id": session.id,
                    "ticket_id": ticket.id if ticket else session.ticket_id,
                    "ticket_redmine_id": ticket.redmine_ticket_id if ticket else None,
                    "ticket_subject": ticket.subject if ticket else None,
                    "started_at": session.started_at.isoformat() if session.started_at else None,
                    "duration_minutes": duration_minutes,
                    "is_running": True,
                }
            )
        return result

    def get_work_summary(self, ticket_id: int) -> Dict:
        """Return full work-session summary for a ticket."""
        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        sessions = (
            self.db.query(WorkSession)
            .filter(WorkSession.ticket_id == ticket_id)
            .order_by(WorkSession.started_at.asc())
            .all()
        )

        now = datetime.now(tz.utc)
        session_list: List[Dict] = []
        active_session_payload: Optional[Dict] = None

        for session in sessions:
            duration = session.duration_minutes or 0
            if session.is_active and session.started_at:
                duration = int((now - session.started_at).total_seconds() / 60)

            payload = {
                "id": session.id,
                "type": _enum_value(session.session_type),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "duration_minutes": duration,
                "is_active": session.is_active,
                "notes": session.notes,
                "paused_reason": session.paused_reason,
            }
            session_list.append(payload)

            if session.is_active:
                active_session_payload = payload

        return {
            "ticket_id": ticket.id,
            "redmine_ticket_id": ticket.redmine_ticket_id,
            "work_started_at": ticket.work_started_at.isoformat() if ticket.work_started_at else None,
            "total_work_minutes": ticket.total_work_minutes or 0,
            "total_waiting_minutes": ticket.total_waiting_minutes or 0,
            "total_idle_minutes": ticket.total_idle_minutes or 0,
            "work_efficiency_percent": ticket.work_efficiency_percent,
            "work_sessions": session_list,
            "active_session": active_session_payload,
        }

    # ------------------------------------------------------------------ #
    # Engineer status helpers
    # ------------------------------------------------------------------ #
    def update_assigned_tickets_count(self, member_id: int, commit: bool = True) -> None:
        """Refresh the assigned ticket count for an engineer."""
        status = self._get_or_create_work_status(member_id)
        assigned_count = (
            self.db.query(TicketHistory)
            .filter(
                TicketHistory.assigned_to_id == member_id,
                TicketHistory.status.in_(
                    [
                        TicketStatus.ASSIGNED,
                        TicketStatus.IN_PROGRESS,
                        TicketStatus.PENDING,
                        TicketStatus.REOPENED,
                    ]
                ),
            )
            .count()
        )
        status.assigned_tickets_count = assigned_count
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    # ------------------------------------------------------------------ #
    # Internal utilities
    # ------------------------------------------------------------------ #
    def _get_or_create_work_status(self, member_id: int) -> EngineerWorkStatus:
        status = (
            self.db.query(EngineerWorkStatus)
            .filter(EngineerWorkStatus.team_member_id == member_id)
            .first()
        )
        if not status:
            status = EngineerWorkStatus(team_member_id=member_id)
            self.db.add(status)
            self.db.flush()
        return status

    def _get_next_session_number(self, ticket_id: int) -> int:
        count = (
            self.db.query(WorkSession)
            .filter(WorkSession.ticket_id == ticket_id)
            .count()
        )
        return count + 1

    def _end_idle_session(self, ticket_id: int, end_time: Optional[datetime] = None) -> None:
        idle_session = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.ticket_id == ticket_id,
                WorkSession.is_active.is_(True),
                WorkSession.session_type == SessionType.IDLE,
            )
            .first()
        )
        if idle_session:
            self._finalize_session(idle_session, end_time or datetime.now(tz.utc))

    def _map_waiting_reason(self, reason: str) -> SessionType:
        try:
            session_type = SessionType(reason)
        except ValueError as exc:
            raise ValueError(f"Unsupported waiting reason '{reason}'") from exc

        if session_type not in WAITING_SESSION_TYPES:
            raise ValueError(f"Reason '{reason}' is not a valid waiting category")

        return session_type

    def _finalize_all_active_sessions(
        self,
        ticket_id: int,
        end_time: Optional[datetime] = None,
    ) -> None:
        now = end_time or datetime.now(tz.utc)
        active_sessions = (
            self.db.query(WorkSession)
            .filter(WorkSession.ticket_id == ticket_id, WorkSession.is_active.is_(True))
            .all()
        )

        for session in active_sessions:
            self._finalize_session(session, now)

        ticket = self.db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()
        if ticket:
            ticket.active_work_session_id = None
            ticket.last_work_session_at = now

    def _finalize_session(self, session: WorkSession, end_time: datetime) -> None:
        if not session.is_active:
            return

        start_time = session.started_at or end_time
        duration_minutes = max(0, int((end_time - start_time).total_seconds() / 60))

        session.ended_at = end_time
        session.is_active = False
        session.duration_minutes = duration_minutes

        ticket = session.ticket or self.db.query(TicketHistory).filter(
            TicketHistory.id == session.ticket_id
        ).first()

        if ticket:
            ticket.total_work_minutes = ticket.total_work_minutes or 0
            ticket.total_waiting_minutes = ticket.total_waiting_minutes or 0
            ticket.total_idle_minutes = ticket.total_idle_minutes or 0

            if session.session_type == SessionType.ACTIVE_WORK:
                ticket.total_work_minutes += duration_minutes
            elif session.session_type in WAITING_SESSION_TYPES:
                ticket.total_waiting_minutes += duration_minutes
            elif session.session_type == SessionType.IDLE:
                ticket.total_idle_minutes += duration_minutes

            total_elapsed = ticket.total_work_minutes + ticket.total_waiting_minutes
            ticket.work_efficiency_percent = (
                (ticket.total_work_minutes / total_elapsed * 100) if total_elapsed > 0 else None
            )

            ticket.actual_resolution_hours = ticket.total_work_minutes / 60.0
            if ticket.active_work_session_id == session.id:
                ticket.active_work_session_id = None
            ticket.last_work_session_at = end_time

        status = self._get_or_create_work_status(session.team_member_id)
        if session.session_type == SessionType.ACTIVE_WORK:
            status.total_work_minutes_today = (status.total_work_minutes_today or 0) + duration_minutes
        elif session.session_type in WAITING_SESSION_TYPES:
            status.total_waiting_minutes_today = (status.total_waiting_minutes_today or 0) + duration_minutes
        elif session.session_type == SessionType.IDLE:
            status.total_idle_minutes_today = (status.total_idle_minutes_today or 0) + duration_minutes

        status.last_activity_at = end_time
        self.db.flush()
        self._recompute_engineer_state(session.team_member_id, reference_time=end_time)

    def _recompute_engineer_state(
        self,
        member_id: int,
        reference_time: Optional[datetime] = None,
        force_idle: bool = False,
    ) -> None:
        """
        Refresh engineered cached metrics (active sessions, idle state, capacity).
        """
        now = reference_time or datetime.now(tz.utc)
        status = self._get_or_create_work_status(member_id)

        active_work_sessions = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.team_member_id == member_id,
                WorkSession.is_active.is_(True),
                WorkSession.session_type == SessionType.ACTIVE_WORK,
            )
            .count()
        )
        status.active_work_sessions_count = active_work_sessions

        assigned_count = (
            self.db.query(TicketHistory)
            .filter(
                TicketHistory.assigned_to_id == member_id,
                TicketHistory.status.in_(
                    [
                        TicketStatus.ASSIGNED,
                        TicketStatus.IN_PROGRESS,
                        TicketStatus.PENDING,
                        TicketStatus.REOPENED,
                    ]
                ),
            )
            .count()
        )
        status.assigned_tickets_count = assigned_count
        status.can_accept_work = active_work_sessions < status.max_concurrent_sessions
        status.last_activity_at = now

        if active_work_sessions == 0:
            if assigned_count > 0 or force_idle:
                if not status.is_idle:
                    status.idle_since = status.idle_since or now
                status.is_idle = True
            else:
                status.is_idle = False
                status.idle_since = None
        else:
            status.is_idle = False
            status.idle_since = None

        self.db.flush()
