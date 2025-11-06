#!/usr/bin/env python3
"""
Scheduling models for shifts and leave management.
"""

from datetime import date
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    Text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.team import TeamLevel


class ShiftAssignment(Base):
    """Recurring shift configuration for a team member."""

    __tablename__ = "shift_assignments"

    id = Column(Integer, primary_key=True, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Optional logical grouping (L1/L2/L3 or other labels)
    team_level = Column(String(10))

    # Day of week (0=Monday, 6=Sunday); null => applies every day
    day_of_week = Column(SmallInteger, nullable=True)

    # Shift window (24h clock). Minutes allow finer control without requiring HH:mm strings.
    start_hour = Column(SmallInteger, nullable=False)
    start_minute = Column(SmallInteger, default=0, nullable=False)
    end_hour = Column(SmallInteger, nullable=False)
    end_minute = Column(SmallInteger, default=0, nullable=False)

    # Timezone for shift calculation
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)

    # Effective window (inclusive)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)

    priority = Column(SmallInteger, default=50, nullable=False)  # Lower number = higher priority
    is_active = Column(Boolean, default=True, index=True, nullable=False)
    notes = Column(Text)
    category = Column(String(20), default="standard", index=True)
    generated_week_start = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    team_member = relationship("TeamMember", back_populates="shift_assignments")

    def __repr__(self):
        return (
            f"<ShiftAssignment(member_id={self.team_member_id}, "
            f"day={self.day_of_week}, {self.start_hour}:{self.start_minute:02d}-"
            f"{self.end_hour}:{self.end_minute:02d})>"
        )

    def applies_on(self, target_date: date) -> bool:
        """Check whether the shift is effective for the given date."""
        if not self.is_active:
            return False

        if self.effective_from and target_date < self.effective_from:
            return False

        if self.effective_to and target_date > self.effective_to:
            return False

        if self.day_of_week is not None and target_date.weekday() != self.day_of_week:
            return False

        return True


class LeaveStatus(str, enum.Enum):
    """Status for leave entries."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeaveType(str, enum.Enum):
    """Supported leave types."""

    VACATION = "vacation"
    SICK = "sick"
    TRAINING = "training"
    UNPLANNED = "unplanned"
    OTHER = "other"


class MemberLeave(Base):
    """Leave / out-of-office entries for team members."""

    __tablename__ = "member_leaves"

    id = Column(Integer, primary_key=True, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String(50), default=LeaveType.OTHER.value, nullable=False)
    status = Column(String(20), default=LeaveStatus.PENDING.value, nullable=False)
    reason = Column(Text)

    created_by = Column(String(200))
    approved_by = Column(String(200))
    approved_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    team_member = relationship("TeamMember", back_populates="leaves")

    def __repr__(self):
        return (
            f"<MemberLeave(member_id={self.team_member_id}, "
            f"{self.start_date} -> {self.end_date}, status={self.status})>"
        )


class OnCallRotationEntry(Base):
    """Rotation order for on-call scheduling per team level."""

    __tablename__ = "oncall_rotation_entries"

    id = Column(Integer, primary_key=True, index=True)
    team_level = Column(String(10), nullable=False, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = Column(SmallInteger, nullable=False, default=0)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    team_member = relationship("TeamMember", back_populates="oncall_rotation_entries")

    def __repr__(self):
        return f"<OnCallRotationEntry(team={self.team_level}, member={self.team_member_id}, position={self.position})>"


class OnCallAssignmentStatus(str, enum.Enum):
    """State of an on-call assignment slot."""

    SCHEDULED = "scheduled"
    REPLACED = "replaced"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class OnCallAssignment(Base):
    """Weekly on-call assignment for a team member."""

    __tablename__ = "oncall_assignments"

    id = Column(Integer, primary_key=True, index=True)
    team_level = Column(String(10), nullable=False, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    status = Column(String(20), default=OnCallAssignmentStatus.SCHEDULED.value, nullable=False, index=True)
    rotation_position = Column(SmallInteger, nullable=True)
    replaced_by_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="SET NULL"), nullable=True)
    replaces_assignment_id = Column(Integer, ForeignKey("oncall_assignments.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    team_member = relationship("TeamMember", foreign_keys=[team_member_id], back_populates="oncall_assignments")
    replaced_by_member = relationship("TeamMember", foreign_keys=[replaced_by_member_id])
    replaces_assignment = relationship("OnCallAssignment", remote_side=[id])

    def __repr__(self):
        return (
            f"<OnCallAssignment(team={self.team_level}, member={self.team_member_id}, "
            f"week_start={self.week_start}, status={self.status})>"
        )


class OnCallRotationState(Base):
    """State pointer for rotation lists per team level."""

    __tablename__ = "oncall_rotation_state"

    id = Column(Integer, primary_key=True, index=True)
    team_level = Column(String(10), unique=True, nullable=False)
    next_position = Column(SmallInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<OnCallRotationState(team={self.team_level}, next={self.next_position})>"
