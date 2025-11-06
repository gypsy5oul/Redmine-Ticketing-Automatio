#!/usr/bin/env python3
"""
Admin user model for portal authentication
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class UserRole(str, enum.Enum):
    """User roles for admin portal"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class User(Base):
    """Admin portal users"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(200))

    # Role and permissions
    role = Column(Enum(UserRole, name='user_role'), default=UserRole.VIEWER, nullable=False)
    active = Column(Boolean, default=True, index=True)

    # Two-factor authentication
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(200))

    # Session management
    last_login = Column(DateTime(timezone=True))
    last_activity = Column(DateTime(timezone=True))
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
    force_password_change = Column(Boolean, default=True, index=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(200))

    team_member = relationship(
        "TeamMember",
        back_populates="user",
        uselist=False
    )

    def __repr__(self):
        return f"<User(username={self.username}, role={self.role})>"

    @property
    def is_locked(self) -> bool:
        """Check if account is locked"""
        from datetime import datetime, timezone

        if self.locked_until:
            return datetime.now(timezone.utc) < self.locked_until
        return False

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        role_permissions = {
            UserRole.SUPER_ADMIN: ["*"],  # All permissions
            UserRole.ADMIN: [
                "view_dashboard",
                "manage_team",
                "manage_sla",
                "manage_escalation",
                "view_analytics",
                "manage_settings",
            ],
            UserRole.MANAGER: [
                "view_dashboard",
                "view_team",
                "view_sla",
                "manual_escalation",
                "view_analytics",
            ],
            UserRole.VIEWER: [
                "view_dashboard",
                "view_team",
                "view_analytics",
            ],
        }

        user_perms = role_permissions.get(self.role, [])
        return "*" in user_perms or permission in user_perms
