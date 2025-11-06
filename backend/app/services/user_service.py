#!/usr/bin/env python3
"""
User Service - Handle user authentication and management
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from loguru import logger

from app.models.user import User, UserRole
from app.core.security import verify_password, get_password_hash


class UserService:
    """Service for user authentication and management"""

    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        # Find user by username or email
        user = self.db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user:
            logger.warning(f"❌ Authentication failed: User '{username}' not found")
            return None

        # Check if account is locked
        if user.is_locked:
            logger.warning(f"🔒 Authentication failed: User '{username}' is locked until {user.locked_until}")
            return None

        # Check if account is active
        if not user.active:
            logger.warning(f"⚠️ Authentication failed: User '{username}' is inactive")
            return None

        # Verify password
        if not verify_password(password, user.hashed_password):
            logger.warning(f"❌ Authentication failed: Invalid password for user '{username}'")
            self.increment_failed_attempts(user.id)
            return None

        # Authentication successful
        logger.info(f"✅ User '{username}' authenticated successfully")
        self.reset_failed_attempts(user.id)
        self.update_last_login(user.id)
        return user

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.VIEWER,
        created_by: Optional[str] = None
    ) -> User:
        """
        Create a new user

        Args:
            username: Unique username
            email: Unique email address
            password: Plain text password (will be hashed)
            full_name: User's full name
            role: User role (default: VIEWER)
            created_by: Username of creator

        Returns:
            Created User object

        Raises:
            ValueError: If username or email already exists
        """
        # Check if username exists
        if self.get_by_username(username):
            raise ValueError(f"Username '{username}' already exists")

        # Check if email exists
        if self.get_by_email(email):
            raise ValueError(f"Email '{email}' already exists")

        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=role,
            active=True,
            two_factor_enabled=False,
            failed_login_attempts=0,
            created_by=created_by,
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        logger.info(f"✅ User '{username}' created successfully with role '{role.value}'")
        return user

    def update_password(self, user_id: int, new_password: str) -> bool:
        """
        Update user password

        Args:
            user_id: User ID
            new_password: New plain text password

        Returns:
            True if successful
        """
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"✅ Password updated for user '{user.username}'")
        return True

    def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        user = self.get_by_id(user_id)
        if user:
            user.last_login = datetime.now(timezone.utc)
            self.db.commit()

    def update_last_activity(self, user_id: int):
        """Update user's last activity timestamp"""
        user = self.get_by_id(user_id)
        if user:
            user.last_activity = datetime.now(timezone.utc)
            self.db.commit()

    def increment_failed_attempts(self, user_id: int):
        """
        Increment failed login attempts and lock account if threshold reached

        Locks account for 30 minutes after 5 failed attempts
        """
        user = self.get_by_id(user_id)
        if not user:
            return

        user.failed_login_attempts += 1

        # Lock account after 5 failed attempts
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
            logger.warning(f"🔒 User '{user.username}' locked for 30 minutes after 5 failed attempts")

        self.db.commit()

    def reset_failed_attempts(self, user_id: int):
        """Reset failed login attempts counter"""
        user = self.get_by_id(user_id)
        if user:
            user.failed_login_attempts = 0
            user.locked_until = None
            self.db.commit()

    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.active = False
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"⚠️ User '{user.username}' deactivated")
        return True

    def activate_user(self, user_id: int) -> bool:
        """Activate a user account"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.active = True
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"✅ User '{user.username}' activated")
        return True

    def change_role(self, user_id: int, new_role: UserRole) -> bool:
        """Change user role"""
        user = self.get_by_id(user_id)
        if not user:
            return False

        old_role = user.role
        user.role = new_role
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        logger.info(f"✅ User '{user.username}' role changed from '{old_role.value}' to '{new_role.value}'")
        return True
