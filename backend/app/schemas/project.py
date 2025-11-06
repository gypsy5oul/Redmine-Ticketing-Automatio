#!/usr/bin/env python3
"""
Schemas for project-level analytics.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectSummary(BaseModel):
    """High-level snapshot for a Jira project."""

    project_jira_id: str = Field(..., description="Normalized Jira project identifier")
    total_tickets: int = Field(..., ge=0)
    open_tickets: int = Field(..., ge=0)
    resolved_tickets: int = Field(..., ge=0)
    breached_tickets: int = Field(..., ge=0)
    sla_compliance_rate: float = Field(..., ge=0.0, le=100.0)
    active_engineers: int = Field(..., ge=0)
    last_activity: Optional[datetime] = Field(None)


class ProjectStatusBreakdown(BaseModel):
    """Ticket counts grouped by status."""

    status: str
    count: int


class ProjectPriorityBreakdown(BaseModel):
    """Ticket counts grouped by priority."""

    priority: str
    count: int


class ProjectTeamContributor(BaseModel):
    """Contribution metrics for an engineer working on the project."""

    member_id: int
    name: str
    email: Optional[str]
    total_tickets: int
    resolved_tickets: int
    sla_compliance_rate: float


class ProjectRecentTicket(BaseModel):
    """Lightweight ticket record for project detail view."""

    ticket_id: int
    redmine_ticket_id: int
    subject: str
    status: str
    priority: str
    assigned_to: Optional[str]
    sla_breached: bool
    created_at: datetime
    resolved_at: Optional[datetime]


class ProjectDetail(BaseModel):
    """Detailed analytics for a single Jira project."""

    summary: ProjectSummary
    status_breakdown: List[ProjectStatusBreakdown]
    priority_breakdown: List[ProjectPriorityBreakdown]
    team_contributors: List[ProjectTeamContributor]
    recent_tickets: List[ProjectRecentTicket]
    trend: List["ProjectTrendPoint"]
    ai_insights: Optional[str] = None


class ProjectTrendPoint(BaseModel):
    """Daily metrics for trend charts."""

    date: datetime
    created: int
    resolved: int
    breached: int
    sla_compliance_rate: float


class ProjectSummaryListResponse(BaseModel):
    """Envelope for project summary collection."""

    projects: List[ProjectSummary]
    count: int


class ProjectDetailResponse(BaseModel):
    """Envelope for project detail."""

    project: ProjectDetail
