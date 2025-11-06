"""
Activity Tracker Service
Tracks and broadcasts system activities in real-time
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
from loguru import logger

from app.models.activity import Activity, ActivityType


class ActivityTracker:
    """Service for tracking and retrieving system activities"""

    def __init__(self, db: Session):
        self.db = db

    def record_activity(
        self,
        activity_type: ActivityType,
        title: str,
        description: Optional[str] = None,
        ticket_id: Optional[int] = None,
        user_id: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None
    ) -> Activity:
        """
        Record a new activity

        Args:
            activity_type: Type of activity
            title: Activity title
            description: Activity description
            ticket_id: Related ticket ID
            user_id: User who performed the activity
            extra_data: Additional extra_data as dict
            icon: Icon identifier
            color: Color code

        Returns:
            Created Activity object
        """
        try:
            # Auto-assign icons and colors based on activity type
            if not icon:
                icon = self._get_default_icon(activity_type)
            if not color:
                color = self._get_default_color(activity_type)

            activity = Activity(
                activity_type=activity_type,
                title=title,
                description=description,
                ticket_id=ticket_id,
                user_id=user_id,
                extra_data=json.dumps(extra_data) if extra_data else None,
                icon=icon,
                color=color,
                created_at=datetime.utcnow()
            )

            self.db.add(activity)
            self.db.commit()
            self.db.refresh(activity)

            logger.debug(f"📝 Activity recorded: {activity_type.value} - {title}")

            return activity

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Failed to record activity: {e}")
            raise

    def get_recent_activities(
        self,
        limit: int = 50,
        activity_types: Optional[List[ActivityType]] = None,
        hours: int = 24
    ) -> List[Activity]:
        """
        Get recent activities

        Args:
            limit: Maximum number of activities to return
            activity_types: Filter by activity types
            hours: Get activities from last N hours

        Returns:
            List of Activity objects
        """
        try:
            query = self.db.query(Activity)

            # Filter by time
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(Activity.created_at >= cutoff_time)

            # Filter by activity types if provided
            if activity_types:
                query = query.filter(Activity.activity_type.in_(activity_types))

            # Order by most recent first
            query = query.order_by(Activity.created_at.desc())

            # Limit results
            activities = query.limit(limit).all()

            return activities

        except Exception as e:
            logger.error(f"❌ Failed to fetch activities: {e}")
            return []

    def get_ticket_activities(self, ticket_id: int, limit: int = 20) -> List[Activity]:
        """Get activities for a specific ticket"""
        try:
            activities = self.db.query(Activity).filter(
                Activity.ticket_id == ticket_id
            ).order_by(Activity.created_at.desc()).limit(limit).all()

            return activities

        except Exception as e:
            logger.error(f"❌ Failed to fetch ticket activities: {e}")
            return []

    def get_user_activities(self, user_id: int, limit: int = 20) -> List[Activity]:
        """Get activities for a specific user"""
        try:
            activities = self.db.query(Activity).filter(
                Activity.user_id == user_id
            ).order_by(Activity.created_at.desc()).limit(limit).all()

            return activities

        except Exception as e:
            logger.error(f"❌ Failed to fetch user activities: {e}")
            return []

    def cleanup_old_activities(self, days: int = 30) -> int:
        """
        Clean up activities older than specified days

        Args:
            days: Delete activities older than N days

        Returns:
            Number of activities deleted
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            deleted_count = self.db.query(Activity).filter(
                Activity.created_at < cutoff_date
            ).delete()

            self.db.commit()

            logger.info(f"🧹 Cleaned up {deleted_count} old activities (older than {days} days)")

            return deleted_count

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Failed to cleanup activities: {e}")
            return 0

    @staticmethod
    def _get_default_icon(activity_type: ActivityType) -> str:
        """Get default icon for activity type"""
        icon_map = {
            ActivityType.TICKET_CREATED: "add_circle",
            ActivityType.TICKET_ASSIGNED: "person_add",
            ActivityType.TICKET_UPDATED: "edit",
            ActivityType.TICKET_RESOLVED: "check_circle",
            ActivityType.TICKET_ESCALATED: "trending_up",
            ActivityType.SLA_WARNING: "warning",
            ActivityType.SLA_CRITICAL: "error",
            ActivityType.SLA_BREACHED: "cancel",
            ActivityType.COMMENT_ADDED: "comment",
            ActivityType.COLLABORATION_ADDED: "group_add",
            ActivityType.MEMBER_ADDED: "person_add",
            ActivityType.MEMBER_UPDATED: "person",
        }
        return icon_map.get(activity_type, "info")

    @staticmethod
    def _get_default_color(activity_type: ActivityType) -> str:
        """Get default color for activity type"""
        color_map = {
            ActivityType.TICKET_CREATED: "#2196f3",  # Blue
            ActivityType.TICKET_ASSIGNED: "#9c27b0",  # Purple
            ActivityType.TICKET_UPDATED: "#ff9800",  # Orange
            ActivityType.TICKET_RESOLVED: "#4caf50",  # Green
            ActivityType.TICKET_ESCALATED: "#f44336",  # Red
            ActivityType.SLA_WARNING: "#ff9800",  # Orange
            ActivityType.SLA_CRITICAL: "#f44336",  # Red
            ActivityType.SLA_BREACHED: "#d32f2f",  # Dark Red
            ActivityType.COMMENT_ADDED: "#00bcd4",  # Cyan
            ActivityType.COLLABORATION_ADDED: "#673ab7",  # Deep Purple
            ActivityType.MEMBER_ADDED: "#4caf50",  # Green
            ActivityType.MEMBER_UPDATED: "#2196f3",  # Blue
        }
        return color_map.get(activity_type, "#757575")  # Grey default


# Helper functions for quick activity recording

def record_ticket_created(db: Session, ticket_id: int, ticket_subject: str, user_id: Optional[int] = None):
    """Record ticket creation activity"""
    tracker = ActivityTracker(db)
    return tracker.record_activity(
        activity_type=ActivityType.TICKET_CREATED,
        title=f"New ticket created: #{ticket_id}",
        description=ticket_subject,
        ticket_id=ticket_id,
        user_id=user_id
    )


def record_ticket_assigned(db: Session, ticket_id: int, ticket_subject: str, user_id: int, user_name: str):
    """Record ticket assignment activity"""
    tracker = ActivityTracker(db)
    return tracker.record_activity(
        activity_type=ActivityType.TICKET_ASSIGNED,
        title=f"Ticket #{ticket_id} assigned to {user_name}",
        description=ticket_subject,
        ticket_id=ticket_id,
        user_id=user_id
    )


def record_ticket_escalated(db: Session, ticket_id: int, ticket_subject: str, from_level: str, to_level: str, user_id: int):
    """Record ticket escalation activity"""
    tracker = ActivityTracker(db)
    return tracker.record_activity(
        activity_type=ActivityType.TICKET_ESCALATED,
        title=f"Ticket #{ticket_id} escalated from {from_level} to {to_level}",
        description=ticket_subject,
        ticket_id=ticket_id,
        user_id=user_id,
        extra_data={"from_level": from_level, "to_level": to_level}
    )


def record_sla_warning(db: Session, ticket_id: int, ticket_subject: str, percentage: float):
    """Record SLA warning activity"""
    tracker = ActivityTracker(db)
    return tracker.record_activity(
        activity_type=ActivityType.SLA_WARNING,
        title=f"SLA warning: Ticket #{ticket_id} at {percentage:.0f}%",
        description=ticket_subject,
        ticket_id=ticket_id,
        extra_data={"completion_percentage": percentage}
    )


def record_sla_critical(db: Session, ticket_id: int, ticket_subject: str, percentage: float):
    """Record SLA critical activity"""
    tracker = ActivityTracker(db)
    return tracker.record_activity(
        activity_type=ActivityType.SLA_CRITICAL,
        title=f"SLA critical: Ticket #{ticket_id} at {percentage:.0f}%",
        description=ticket_subject,
        ticket_id=ticket_id,
        extra_data={"completion_percentage": percentage}
    )
