#!/usr/bin/env python3
"""
SLA policy and tracking models
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class SLAStatus(str, enum.Enum):
    """SLA status"""
    WITHIN_SLA = "within_sla"
    AT_RISK = "at_risk"  # 80% consumed
    CRITICAL = "critical"  # 90% consumed
    BREACHED = "breached"


class SLAPolicy(Base):
    """SLA policies for different priorities"""
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(String(50), unique=True, nullable=False, index=True)

    # Time limits in minutes
    response_time_minutes = Column(Integer, nullable=False)
    resolution_time_minutes = Column(Integer, nullable=False)
    escalation_time_minutes = Column(Integer, nullable=False)

    # Business hours vs 24/7
    business_hours_only = Column(Boolean, default=True)

    # Environment-specific (optional)
    environment = Column(String(50))  # prod, staging, dev, null for all

    # Active status
    active = Column(Boolean, default=True, index=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(200))

    # Relationships
    sla_trackers = relationship("SLATracker", back_populates="policy")

    def __repr__(self):
        return f"<SLAPolicy(priority={self.priority}, resolution={self.resolution_time_minutes}min)>"

    @property
    def response_time_hours(self) -> float:
        return self.response_time_minutes / 60

    @property
    def resolution_time_hours(self) -> float:
        return self.resolution_time_minutes / 60

    @property
    def escalation_time_hours(self) -> float:
        return self.escalation_time_minutes / 60


class SLATracker(Base):
    """Real-time SLA tracking for each ticket"""
    __tablename__ = "sla_trackers"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("ticket_history.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )
    policy_id = Column(Integer, ForeignKey("sla_policies.id"))

    # Status
    status = Column(Enum(SLAStatus, name='sla_status'), default=SLAStatus.WITHIN_SLA, index=True)

    # Deadlines
    response_deadline = Column(DateTime(timezone=True), nullable=False)
    resolution_deadline = Column(DateTime(timezone=True), nullable=False)
    escalation_deadline = Column(DateTime(timezone=True), nullable=False)

    # Actual times
    actual_response_time = Column(DateTime(timezone=True))
    actual_resolution_time = Column(DateTime(timezone=True))

    # Breach tracking
    response_breached = Column(Boolean, default=False)
    resolution_breached = Column(Boolean, default=False)
    escalation_triggered = Column(Boolean, default=False)

    # Time calculations (in minutes)
    response_time_consumed = Column(Integer, default=0)
    resolution_time_consumed = Column(Integer, default=0)
    response_breach_minutes = Column(Integer)
    resolution_breach_minutes = Column(Integer)

    # Pause/Resume (for pending status)
    paused = Column(Boolean, default=False)
    paused_at = Column(DateTime(timezone=True))
    total_paused_minutes = Column(Integer, default=0)

    # Alerts sent
    warning_alert_sent = Column(Boolean, default=False)
    critical_alert_sent = Column(Boolean, default=False)
    breach_alert_sent = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    ticket = relationship("TicketHistory", back_populates="sla_tracker")
    policy = relationship("SLAPolicy", back_populates="sla_trackers")
    breaches = relationship("SLABreach", back_populates="tracker")

    def __repr__(self):
        return f"<SLATracker(ticket_id={self.ticket_id}, status={self.status})>"

    def calculate_time_remaining(self, deadline_type: str) -> int:
        """Calculate minutes remaining until deadline"""
        from datetime import datetime, timezone

        if deadline_type == "response":
            deadline = self.response_deadline
        elif deadline_type == "resolution":
            deadline = self.resolution_deadline
        else:
            deadline = self.escalation_deadline

        if not deadline:
            return 0

        now = datetime.now(timezone.utc)
        delta = deadline - now
        return int(delta.total_seconds() / 60)

    def get_completion_percentage(self, deadline_type: str) -> float:
        """Get percentage of time consumed (0-100)"""
        remaining = self.calculate_time_remaining(deadline_type)
        if remaining <= 0:
            return 100.0

        if deadline_type == "response":
            total = self.policy.response_time_minutes
        else:
            total = self.policy.resolution_time_minutes

        consumed = total - remaining
        return (consumed / total) * 100 if total > 0 else 100.0


class SLABreach(Base):
    """Record of SLA breaches for reporting"""
    __tablename__ = "sla_breaches"

    id = Column(Integer, primary_key=True, index=True)
    tracker_id = Column(Integer, ForeignKey("sla_trackers.id", ondelete="CASCADE"), index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)

    # Breach details
    breach_type = Column(String(50), nullable=False)  # response, resolution
    breach_minutes = Column(Integer, nullable=False)
    priority = Column(String(50), index=True)
    environment = Column(String(50))

    # Assignment at breach time
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"))
    team_level = Column(String(10))

    # Impact
    customer_impact = Column(Text)
    business_impact = Column(Text)

    # Resolution
    root_cause = Column(Text)
    remediation_action = Column(Text)
    prevented_future = Column(Boolean, default=False)

    # Metadata
    breached_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(String(200))

    # Relationships
    tracker = relationship("SLATracker", back_populates="breaches")
    ticket = relationship("TicketHistory")
    assigned_to = relationship("TeamMember")

    def __repr__(self):
        return f"<SLABreach(ticket_id={self.ticket_id}, type={self.breach_type})>"
