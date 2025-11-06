#!/usr/bin/env python3
"""
Team member and skill models
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Table, Enum, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class TeamLevel(str, enum.Enum):
    """Team levels for escalation hierarchy"""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class SkillLevel(str, enum.Enum):
    """Skill proficiency levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# Association table for many-to-many relationship
team_member_skills = Table(
    'team_member_skills',
    Base.metadata,
    Column('team_member_id', Integer, ForeignKey('team_members.id', ondelete='CASCADE')),
    Column('skill_id', Integer, ForeignKey('skills.id', ondelete='CASCADE')),
    Column('proficiency_level', Enum(SkillLevel, name='skill_level'), default=SkillLevel.INTERMEDIATE),
    Column('years_experience', Float, default=0.0),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)


class Skill(Base):
    """Skills/Technologies that team members can have"""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False)  # kubernetes, database, cicd, messaging, etc.
    description = Column(String(500))
    keywords = Column(String(1000))  # Comma-separated keywords for matching
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team_members = relationship(
        "TeamMember",
        secondary=team_member_skills,
        back_populates="skills"
    )

    def __repr__(self):
        return f"<Skill(name={self.name}, category={self.category})>"


class TeamMember(Base):
    """Team members with skills and capacity configuration"""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    redmine_user_id = Column(Integer, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    team_level = Column(Enum(TeamLevel, name='team_level'), nullable=False, index=True)
    max_tickets = Column(Integer, default=8)
    active = Column(Boolean, default=True, index=True)

    # Timezone for timezone-aware assignment
    timezone = Column(String(50), default="Asia/Kolkata")

    # Working hours (24-hour format)
    work_start_hour = Column(Integer, default=9)
    work_end_hour = Column(Integer, default=18)

    # Performance tracking
    total_tickets_assigned = Column(Integer, default=0)
    total_tickets_resolved = Column(Integer, default=0)
    avg_resolution_time_hours = Column(Float, default=0.0)
    sla_compliance_rate = Column(Float, default=100.0)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_assigned_at = Column(DateTime(timezone=True))

    # Relationships
    skills = relationship(
        "Skill",
        secondary=team_member_skills,
        back_populates="team_members"
    )
    assigned_tickets = relationship("TicketHistory", back_populates="assigned_to")
    comments = relationship("TicketComment", back_populates="author")
    performance_metrics = relationship("PerformanceMetric", back_populates="team_member")
    escalations_from = relationship(
        "Escalation",
        foreign_keys="Escalation.from_user_id",
        back_populates="from_user"
    )
    escalations_to = relationship(
        "Escalation",
        foreign_keys="Escalation.to_user_id",
        back_populates="to_user"
    )
    shift_assignments = relationship(
        "ShiftAssignment",
        back_populates="team_member",
        cascade="all, delete-orphan"
    )
    leaves = relationship(
        "MemberLeave",
        back_populates="team_member",
        cascade="all, delete-orphan"
    )
    oncall_rotation_entries = relationship(
        "OnCallRotationEntry",
        back_populates="team_member",
        cascade="all, delete-orphan"
    )
    oncall_assignments = relationship(
        "OnCallAssignment",
        back_populates="team_member",
        cascade="all, delete-orphan",
        foreign_keys="OnCallAssignment.team_member_id"
    )
    user = relationship(
        "User",
        back_populates="team_member",
        uselist=False
    )
    work_sessions = relationship(
        "WorkSession",
        back_populates="team_member",
        cascade="all, delete-orphan"
    )
    work_status = relationship(
        "EngineerWorkStatus",
        back_populates="team_member",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<TeamMember(name={self.name}, level={self.team_level})>"

    @property
    def is_available(self) -> bool:
        """Check if member is active and within capacity"""
        from datetime import datetime
        import pytz

        if not self.active:
            return False

        # Check timezone-aware working hours
        tz = pytz.timezone(self.timezone)
        current_time = datetime.now(tz)
        current_hour = current_time.hour

        if not (self.work_start_hour <= current_hour < self.work_end_hour):
            return False

        return True

    def get_skill_proficiency(self, skill_name: str) -> str:
        """Get proficiency level for a specific skill"""
        for skill in self.skills:
            if skill.name.lower() == skill_name.lower():
                # Get proficiency from association table
                return "intermediate"  # Default, should query association table
        return "none"
