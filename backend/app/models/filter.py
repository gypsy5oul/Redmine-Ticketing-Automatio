#!/usr/bin/env python3
"""
Saved filters for ticket queries
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class SavedTicketFilter(Base):
    """Persisted ticket filter definitions"""

    __tablename__ = "saved_ticket_filters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True, index=True)
    description = Column(String(500))
    filters = Column(JSON, nullable=False)
    created_by = Column(String(150))
    updated_by = Column(String(150))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SavedTicketFilter(name={self.name})>"
