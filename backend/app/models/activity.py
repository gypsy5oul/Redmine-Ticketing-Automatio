"""
Activity Tracking Model
Records all system activities for real-time feed
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class ActivityType(str, enum.Enum):
    """Activity type enumeration"""
    TICKET_CREATED = "ticket_created"
    TICKET_ASSIGNED = "ticket_assigned"
    TICKET_UPDATED = "ticket_updated"
    TICKET_RESOLVED = "ticket_resolved"
    TICKET_ESCALATED = "ticket_escalated"
    SLA_WARNING = "sla_warning"
    SLA_CRITICAL = "sla_critical"
    SLA_BREACHED = "sla_breached"
    COMMENT_ADDED = "comment_added"
    COLLABORATION_ADDED = "collaboration_added"
    MEMBER_ADDED = "member_added"
    MEMBER_UPDATED = "member_updated"


class Activity(Base):
    """Activity log for real-time feed"""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(Enum(ActivityType), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Related entities
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("team_members.id", ondelete="SET NULL"), nullable=True)

    # Metadata
    extra_data = Column(Text, nullable=True)  # JSON string for additional data
    icon = Column(String(50), nullable=True)  # Icon identifier for frontend
    color = Column(String(20), nullable=True)  # Color code for frontend

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    ticket = relationship("TicketHistory", foreign_keys=[ticket_id], backref="activities")
    user = relationship("TeamMember", foreign_keys=[user_id], backref="activities")

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "activity_type": self.activity_type.value,
            "title": self.title,
            "description": self.description,
            "ticket_id": self.ticket_id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else None,
            "extra_data": self.extra_data,
            "icon": self.icon,
            "color": self.color,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
