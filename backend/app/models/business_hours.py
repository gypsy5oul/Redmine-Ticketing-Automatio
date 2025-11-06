#!/usr/bin/env python3
"""
Business hours configuration model
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Time, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class BusinessHours(Base):
    """Business hours configuration for different teams"""
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    team_level = Column(String(10))  # L1, L2, L3, or null for all

    # Daily hours (24-hour format)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)

    # Timezone
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)

    # Days of week (0 = Monday, 6 = Sunday)
    working_days = Column(JSON, default=[0, 1, 2, 3, 4, 5])  # Monday-Saturday

    # Holidays (dates in YYYY-MM-DD format)
    holidays = Column(JSON, default=[])

    # Active status
    active = Column(Boolean, default=True, index=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(200))

    def __repr__(self):
        return f"<BusinessHours(name={self.name}, {self.start_hour}-{self.end_hour})>"

    def is_business_hours(self, dt=None) -> bool:
        """Check if given datetime is within business hours"""
        from datetime import datetime
        import pytz

        if not self.active:
            return False

        if dt is None:
            tz = pytz.timezone(self.timezone)
            dt = datetime.now(tz)

        # Check day of week
        if dt.weekday() not in self.working_days:
            return False

        # Check if holiday
        date_str = dt.strftime("%Y-%m-%d")
        if date_str in self.holidays:
            return False

        # Check hour
        if not (self.start_hour <= dt.hour < self.end_hour):
            return False

        return True
