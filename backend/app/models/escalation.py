#!/usr/bin/env python3
"""
Escalation tracking models
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class EscalationReason(str, enum.Enum):
    """Reasons for escalation"""
    SLA_BREACH = "sla_breach"
    COMPLEXITY = "complexity"
    MANUAL_REQUEST = "manual_request"
    NO_RESPONSE = "no_response"
    SKILL_MISMATCH = "skill_mismatch"
    CAPACITY = "capacity"
    CUSTOMER_REQUEST = "customer_request"
    REOPENED = "reopened"


class EscalationType(str, enum.Enum):
    """Type of escalation"""
    AUTO = "automatic"
    MANUAL = "manual"
    FORCED = "forced"


class Escalation(Base):
    """Escalation history and tracking"""
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("ticket_history.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # From/To assignment
    from_user_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    to_user_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    from_team_level = Column(String(10), nullable=False)
    to_team_level = Column(String(10), nullable=False)

    # Escalation details
    reason = Column(Enum(EscalationReason, name='escalation_reason'), nullable=False, index=True)
    escalation_type = Column(Enum(EscalationType, name='escalation_type'), default=EscalationType.AUTO)
    description = Column(Text)

    # Context at escalation time
    priority_at_escalation = Column(String(50))
    sla_status_at_escalation = Column(String(50))
    time_elapsed_minutes = Column(Integer)

    # Resolution tracking
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))

    # Approval (for manual escalations)
    requires_approval = Column(Boolean, default=False)
    approved = Column(Boolean)
    approved_by = Column(String(200))
    approved_at = Column(DateTime(timezone=True))

    # Metadata
    escalated_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    escalated_by = Column(String(200))  # System or admin name

    # Relationships
    ticket = relationship("TicketHistory", back_populates="escalations")
    from_user = relationship(
        "TeamMember",
        foreign_keys=[from_user_id],
        back_populates="escalations_from"
    )
    to_user = relationship(
        "TeamMember",
        foreign_keys=[to_user_id],
        back_populates="escalations_to"
    )

    def __repr__(self):
        return f"<Escalation(ticket_id={self.ticket_id}, {self.from_team_level}→{self.to_team_level})>"
