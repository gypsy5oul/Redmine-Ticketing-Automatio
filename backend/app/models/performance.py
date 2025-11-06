#!/usr/bin/env python3
"""
Performance tracking and metrics models
"""

from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Float, Text, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class PerformanceMetric(Base):
    """Daily performance metrics per team member"""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    date = Column(Date, nullable=False, index=True)

    # Ticket counts
    tickets_assigned = Column(Integer, default=0)
    tickets_resolved = Column(Integer, default=0)
    tickets_escalated = Column(Integer, default=0)
    tickets_reopened = Column(Integer, default=0)

    # Time metrics (in hours)
    avg_response_time_hours = Column(Float)
    avg_resolution_time_hours = Column(Float)
    total_working_hours = Column(Float)

    # SLA metrics
    sla_met_count = Column(Integer, default=0)
    sla_breached_count = Column(Integer, default=0)
    sla_compliance_rate = Column(Float)  # Percentage

    # Quality metrics
    customer_satisfaction_score = Column(Float)  # 1-5 scale
    first_time_resolution_rate = Column(Float)  # Percentage
    reopened_rate = Column(Float)  # Percentage

    # Collaboration
    collaborative_tickets_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team_member = relationship("TeamMember", back_populates="performance_metrics")

    def __repr__(self):
        return f"<PerformanceMetric(member_id={self.team_member_id}, date={self.date})>"


class TicketResolutionMetric(Base):
    """Detailed metrics for each resolved ticket"""
    __tablename__ = "ticket_resolution_metrics"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(
        Integer,
        ForeignKey("ticket_history.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )

    # Resolution details
    resolution_time_hours = Column(Float, nullable=False)
    first_response_time_minutes = Column(Integer)
    number_of_updates = Column(Integer, default=0)
    number_of_escalations = Column(Integer, default=0)

    # Quality indicators
    reopened = Column(Boolean, default=False)
    reopened_count = Column(Integer, default=0)
    customer_satisfaction = Column(Integer)  # 1-5 rating

    # Effort tracking
    estimated_effort_hours = Column(Float)
    actual_effort_hours = Column(Float)
    effort_accuracy = Column(Float)  # actual/estimated ratio

    # SLA performance
    sla_met = Column(Boolean, default=True)
    sla_buffer_minutes = Column(Integer)  # Positive = within SLA, Negative = breach

    # Collaboration impact
    collaboration_required = Column(Boolean, default=False)
    number_of_collaborators = Column(Integer, default=1)

    # Learning opportunity
    added_to_knowledge_base = Column(Boolean, default=False)
    knowledge_base_article_id = Column(String(100))

    # Metadata
    resolved_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ticket = relationship("TicketHistory", back_populates="resolution_metric")

    def __repr__(self):
        return f"<TicketResolutionMetric(ticket_id={self.ticket_id}, resolution_hours={self.resolution_time_hours})>"
