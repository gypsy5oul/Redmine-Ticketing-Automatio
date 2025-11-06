#!/usr/bin/env python3
"""
Work Session Tracking - Accurate time measurement for tickets
Tracks actual work time vs waiting time for each ticket
"""

from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class SessionType(str, enum.Enum):
    """Types of work sessions"""
    ACTIVE_WORK = "active_work"                    # Engineer actively working
    WAITING_CUSTOMER = "waiting_customer"          # Waiting for customer response
    WAITING_APPROVAL = "waiting_approval"          # Waiting for manager approval
    WAITING_DEPLOYMENT = "waiting_deployment"      # Waiting for deployment window
    WAITING_EXTERNAL = "waiting_external"          # Waiting for external team
    IDLE = "idle"                                  # Ticket assigned but not picked up


class WorkSession(Base):
    """
    Track individual work sessions for tickets

    Each time an engineer starts/pauses/resumes work, a new session is created.
    This allows accurate tracking of actual work time vs waiting time.
    """
    __tablename__ = "work_sessions"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id"), nullable=False, index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"), nullable=False, index=True)

    # Session type
    session_type = Column(String(50), nullable=False, default="active_work", index=True)

    # Time tracking
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True), index=True)
    duration_minutes = Column(Integer)  # Calculated when session ends

    # Session metadata
    is_active = Column(Boolean, default=True, index=True)  # Currently active session
    notes = Column(Text)  # What was done during this session
    paused_reason = Column(String(200))  # Why session was paused (for waiting sessions)

    # Session context
    session_number = Column(Integer, default=1)  # Which session for this ticket (1st, 2nd, etc.)

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ticket = relationship("TicketHistory", back_populates="work_sessions")
    team_member = relationship("TeamMember", back_populates="work_sessions")

    def __repr__(self):
        return f"<WorkSession(id={self.id}, ticket={self.ticket_id}, type={self.session_type}, duration={self.duration_minutes}m)>"


class EngineerWorkStatus(Base):
    """
    Track engineer's current work status and capacity

    This helps track:
    - How many tickets an engineer is actively working on
    - Idle time (assigned tickets but not working)
    - Work patterns and efficiency
    """
    __tablename__ = "engineer_work_status"

    id = Column(Integer, primary_key=True, index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"), nullable=False, unique=True, index=True)

    # Current work status
    active_work_sessions_count = Column(Integer, default=0)  # How many tickets currently working on (max 2)
    assigned_tickets_count = Column(Integer, default=0)      # Total tickets assigned

    # Idle tracking
    is_idle = Column(Boolean, default=False, index=True)     # Has assigned tickets but not working on any
    idle_since = Column(DateTime(timezone=True))             # When idle period started
    total_idle_minutes_today = Column(Integer, default=0)    # Total idle time today

    # Work capacity
    can_accept_work = Column(Boolean, default=True)          # Can accept new work sessions (<2 active)
    max_concurrent_sessions = Column(Integer, default=2)     # Maximum concurrent work sessions

    # Today's summary (reset daily)
    work_started_today_at = Column(DateTime(timezone=True))  # First work session today
    total_work_minutes_today = Column(Integer, default=0)    # Total active work today
    total_waiting_minutes_today = Column(Integer, default=0) # Total waiting time today
    tickets_completed_today = Column(Integer, default=0)     # Tickets resolved today

    # Timestamps
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    team_member = relationship("TeamMember", back_populates="work_status")

    def __repr__(self):
        return f"<EngineerWorkStatus(member={self.team_member_id}, active={self.active_work_sessions_count}, idle={self.is_idle})>"
