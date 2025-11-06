#!/usr/bin/env python3
"""
Ticket tracking and collaboration models
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class TicketStatus(str, enum.Enum):
    """Ticket status"""
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"


class TicketPriority(str, enum.Enum):
    """Ticket priorities"""
    P1_CRITICAL = "P1(Critical)"
    P2_HIGH = "P2(High)"
    P3_MEDIUM = "P3(Medium)"
    P4_LOW = "P4(Low)"
    P5_TRIVIAL = "P5(Trivial)"


class TicketCategory(str, enum.Enum):
    """Ticket categories from ML classification"""
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    NETWORK = "network"
    CICD = "cicd"
    MESSAGING = "messaging"
    STORAGE = "storage"
    APPLICATION = "application"
    SECURITY = "security"
    OTHER = "other"


class ComplexityLevel(str, enum.Enum):
    """Ticket complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"


class TicketHistory(Base):
    """Complete ticket lifecycle tracking"""
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    redmine_ticket_id = Column(Integer, unique=True, nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    description = Column(Text)

    # Requester metadata
    requester_name = Column(String(255))

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    team_level = Column(String(10), nullable=False, index=True)  # Store as String instead

    # Classification
    priority = Column(Enum(TicketPriority, name='ticket_priority'), nullable=False, index=True)
    original_priority = Column(Enum(TicketPriority, name='ticket_priority'))
    priority_adjusted = Column(Boolean, default=False)
    status = Column(Enum(TicketStatus, name='ticket_status'), default=TicketStatus.NEW, index=True)
    environment = Column(String(50), index=True)  # prod, staging, dev
    category = Column(Enum(TicketCategory, name='ticket_category'), index=True)
    complexity = Column(Enum(ComplexityLevel, name='complexity_level'))

    # ML Predictions
    estimated_resolution_hours = Column(Float)
    predicted_escalation_probability = Column(Float)  # 0-1
    ml_confidence_score = Column(Float)  # 0-1

    # SLA Tracking
    sla_deadline = Column(DateTime(timezone=True))
    sla_breached = Column(Boolean, default=False, index=True)
    sla_breach_minutes = Column(Integer)  # How many minutes over SLA

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True))
    first_response_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))

    # Time tracking (legacy)
    actual_resolution_hours = Column(Float)
    time_to_first_response_minutes = Column(Integer)

    # Enhanced work session tracking
    work_started_at = Column(DateTime(timezone=True))  # First time work began
    last_work_session_at = Column(DateTime(timezone=True))  # Last active work timestamp
    total_work_minutes = Column(Integer, default=0)  # Sum of all active work sessions
    total_waiting_minutes = Column(Integer, default=0)  # Sum of all waiting periods
    total_idle_minutes = Column(Integer, default=0)  # Time assigned but not picked up
    active_work_session_id = Column(Integer)  # Currently active session ID
    work_efficiency_percent = Column(Float)  # work_time / (work_time + waiting_time) * 100

    # Escalation tracking
    escalation_count = Column(Integer, default=0)
    escalated = Column(Boolean, default=False, index=True)

    # AI Analysis
    ai_analysis = Column(Text)
    ai_analysis_time_seconds = Column(Float)
    ai_model_used = Column(String(100))

    # Collaboration
    is_collaborative = Column(Boolean, default=False)
    collaborator_count = Column(Integer, default=0)

    # Metadata
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    redmine_url = Column(String(500))
    project_jira_id = Column(String(100), index=True)

    # Relationships
    assigned_to = relationship("TeamMember", back_populates="assigned_tickets")
    sla_tracker = relationship("SLATracker", back_populates="ticket", uselist=False)
    escalations = relationship("Escalation", back_populates="ticket")
    collaborations = relationship("TicketCollaboration", back_populates="ticket")
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    resolution_metric = relationship(
        "TicketResolutionMetric",
        back_populates="ticket",
        uselist=False
    )
    work_sessions = relationship(
        "WorkSession",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="WorkSession.started_at"
    )
    resolution_notes = Column(Text)

    def __repr__(self):
        return f"<TicketHistory(id={self.redmine_ticket_id}, priority={self.priority})>"


class TicketCollaboration(Base):
    """Track multiple engineers collaborating on tickets"""
    __tablename__ = "ticket_collaborations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"))

    # Collaboration details
    role = Column(String(50))  # primary, secondary, consultant, observer
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    # Contribution tracking
    comments_count = Column(Integer, default=0)
    time_spent_hours = Column(Float, default=0.0)
    contribution_percentage = Column(Float)  # 0-100

    # Notes
    notes = Column(Text)

    # Relationships
    ticket = relationship("TicketHistory", back_populates="collaborations")
    team_member = relationship("TeamMember")

    def __repr__(self):
        return f"<TicketCollaboration(ticket_id={self.ticket_id}, member={self.team_member_id})>"


class CommentType(str, enum.Enum):
    """Comment visibility types"""
    PUBLIC = "public"  # Visible to customer
    INTERNAL = "internal"  # Only visible to team


class TicketComment(Base):
    """Ticket comments and internal notes"""
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("team_members.id", ondelete="SET NULL"), index=True)

    # Comment content
    content = Column(Text, nullable=False)
    comment_type = Column(Enum(CommentType, name='comment_type', values_callable=lambda x: [e.value for e in x]), default=CommentType.PUBLIC, nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    edited = Column(Boolean, default=False)

    # Attachments reference (for future enhancement)
    has_attachments = Column(Boolean, default=False)
    attachment_count = Column(Integer, default=0)

    # Relationships
    ticket = relationship("TicketHistory", back_populates="comments")
    author = relationship("TeamMember", back_populates="comments")

    def __repr__(self):
        return f"<TicketComment(id={self.id}, ticket_id={self.ticket_id}, type={self.comment_type})>"
