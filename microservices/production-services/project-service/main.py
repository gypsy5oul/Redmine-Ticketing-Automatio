#!/usr/bin/env python3
"""
Project Service - Project analytics and metrics

Port: 8011
Features:
- Project summaries list
- Project detail view
- Aggregates data from ticket_history table

Source: /backend/app/api/v1/projects.py
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Text, func, case, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Import shared auth and logging utilities
from shared.auth_utils import (
    setup_logging,
    log_request,
    log_error,
    get_current_user,
    User
)

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    SERVICE_NAME: str = "project-service"
    SERVICE_PORT: int = 8011

settings = Settings()

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Project Service", version="1.0.0")

# Setup enhanced logging with request tracking
logger = setup_logging("project-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# RESPONSE MODELS
# ============================================================================

class ProjectSummary(BaseModel):
    project_jira_id: str
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    breached_tickets: int
    sla_compliance_rate: float
    active_engineers: int
    last_activity: Optional[datetime]

class ProjectSummaryListResponse(BaseModel):
    projects: List[ProjectSummary]
    count: int

class ProjectStatusBreakdown(BaseModel):
    status: str
    count: int

class ProjectPriorityBreakdown(BaseModel):
    priority: str
    count: int

class ProjectTeamContributor(BaseModel):
    engineer_name: str
    tickets_handled: int

class ProjectRecentTicket(BaseModel):
    ticket_id: int
    redmine_id: int
    subject: str
    status: str
    priority: str
    assigned_to: Optional[str]
    created_at: datetime

class ProjectTrendPoint(BaseModel):
    date: str
    created: int
    resolved: int

class ProjectDetail(BaseModel):
    project_jira_id: str
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    breached_tickets: int
    sla_compliance_rate: float
    active_engineers: int
    last_activity: Optional[datetime]
    status_breakdown: List[ProjectStatusBreakdown]
    priority_breakdown: List[ProjectPriorityBreakdown]
    team_contributors: List[ProjectTeamContributor]
    recent_tickets: List[ProjectRecentTicket]
    trend_data: List[ProjectTrendPoint]
    ai_insights: Optional[str] = None

class ProjectDetailResponse(BaseModel):
    project: ProjectDetail

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}


@app.get("/api/v1/projects", response_model=ProjectSummaryListResponse, tags=["Projects"])
async def list_projects(
    user: User = Depends(get_current_user),
    request: Request = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    List all Jira projects with ticket metrics - Requires: Any authenticated user
    Source: /backend/app/api/v1/projects.py:22-38
    """
    log_request(logger, request, user.id, "GET /api/v1/projects")
    try:
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        ticket_history = Table('ticket_history', metadata, autoload_with=engine)

        # Define open and resolved statuses
        OPEN_STATUSES = ['new', 'assigned', 'in_progress', 'pending', 'reopened']
        RESOLVED_STATUSES = ['resolved', 'closed']

        # Aggregate query
        query = db.query(
            ticket_history.c.project_jira_id.label("project_jira_id"),
            func.count(ticket_history.c.id).label("total_tickets"),
            func.sum(
                case(
                    (ticket_history.c.status.in_(OPEN_STATUSES), 1),
                    else_=0
                )
            ).label("open_tickets"),
            func.sum(
                case(
                    (ticket_history.c.status.in_(RESOLVED_STATUSES), 1),
                    else_=0
                )
            ).label("resolved_tickets"),
            func.sum(
                case(
                    (ticket_history.c.sla_breached == True, 1),
                    else_=0
                )
            ).label("breached_tickets"),
            func.count(func.distinct(ticket_history.c.assigned_to_id)).label("active_engineers"),
            func.max(
                func.coalesce(
                    ticket_history.c.updated_at,
                    ticket_history.c.resolved_at,
                    ticket_history.c.created_at
                )
            ).label("last_activity"),
            func.sum(
                case(
                    (
                        and_(
                            ticket_history.c.resolved_at.isnot(None),
                            ticket_history.c.sla_breached == False
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("resolved_on_time")
        ).filter(
            ticket_history.c.project_jira_id.isnot(None)
        ).group_by(
            ticket_history.c.project_jira_id
        )

        results = query.all()

        summaries = []
        for row in results:
            resolved_tickets = row.resolved_tickets or 0
            resolved_on_time = row.resolved_on_time or 0

            compliance_rate = (
                (resolved_on_time / resolved_tickets) * 100 if resolved_tickets else 100.0
            )

            summaries.append(ProjectSummary(
                project_jira_id=row.project_jira_id,
                total_tickets=row.total_tickets or 0,
                open_tickets=row.open_tickets or 0,
                resolved_tickets=resolved_tickets,
                breached_tickets=row.breached_tickets or 0,
                sla_compliance_rate=round(compliance_rate, 2),
                active_engineers=row.active_engineers or 0,
                last_activity=row.last_activity
            ))

        # Sort by last activity
        summaries.sort(key=lambda x: x.last_activity or datetime.min, reverse=True)

        # Apply limit
        if limit and len(summaries) > limit:
            summaries = summaries[:limit]

        logger.info(f"✅ Retrieved {len(summaries)} project summaries")

        return ProjectSummaryListResponse(projects=summaries, count=len(summaries))

    except Exception as e:
        logger.error(f"❌ Failed to get project summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/projects/{project_jira_id}", response_model=ProjectDetailResponse, tags=["Projects"])
async def get_project_detail(
    project_jira_id: str,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Get detailed metrics for a Jira project - Requires: Any authenticated user
    Source: /backend/app/api/v1/projects.py:41-61
    """
    log_request(logger, request, user.id, f"GET /api/v1/projects/{project_jira_id}")
    try:
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        ticket_history = Table('ticket_history', metadata, autoload_with=engine)
        team_members = Table('team_members', metadata, autoload_with=engine)

        # Get base summary
        OPEN_STATUSES = ['new', 'assigned', 'in_progress', 'pending', 'reopened']
        RESOLVED_STATUSES = ['resolved', 'closed']

        summary_query = db.query(
            func.count(ticket_history.c.id).label("total_tickets"),
            func.sum(case((ticket_history.c.status.in_(OPEN_STATUSES), 1), else_=0)).label("open_tickets"),
            func.sum(case((ticket_history.c.status.in_(RESOLVED_STATUSES), 1), else_=0)).label("resolved_tickets"),
            func.sum(case((ticket_history.c.sla_breached == True, 1), else_=0)).label("breached_tickets"),
            func.count(func.distinct(ticket_history.c.assigned_to_id)).label("active_engineers"),
            func.max(func.coalesce(ticket_history.c.updated_at, ticket_history.c.created_at)).label("last_activity"),
            func.sum(case((and_(ticket_history.c.resolved_at.isnot(None), ticket_history.c.sla_breached == False), 1), else_=0)).label("resolved_on_time")
        ).filter(
            ticket_history.c.project_jira_id == project_jira_id
        ).first()

        if not summary_query or summary_query.total_tickets == 0:
            raise HTTPException(status_code=404, detail="Project not found")

        # Status breakdown
        status_query = db.query(
            ticket_history.c.status,
            func.count(ticket_history.c.id).label("count")
        ).filter(
            ticket_history.c.project_jira_id == project_jira_id
        ).group_by(
            ticket_history.c.status
        ).all()

        status_breakdown = [
            ProjectStatusBreakdown(status=row.status, count=row.count)
            for row in status_query
        ]

        # Priority breakdown
        priority_query = db.query(
            ticket_history.c.priority,
            func.count(ticket_history.c.id).label("count")
        ).filter(
            ticket_history.c.project_jira_id == project_jira_id
        ).group_by(
            ticket_history.c.priority
        ).all()

        priority_breakdown = [
            ProjectPriorityBreakdown(priority=row.priority, count=row.count)
            for row in priority_query
        ]

        # Team contributors
        contributor_query = db.query(
            team_members.c.name.label("engineer_name"),
            func.count(ticket_history.c.id).label("tickets_handled")
        ).join(
            ticket_history,
            ticket_history.c.assigned_to_id == team_members.c.id
        ).filter(
            ticket_history.c.project_jira_id == project_jira_id
        ).group_by(
            team_members.c.name
        ).order_by(
            func.count(ticket_history.c.id).desc()
        ).limit(10).all()

        team_contributors = [
            ProjectTeamContributor(engineer_name=row.engineer_name, tickets_handled=row.tickets_handled)
            for row in contributor_query
        ]

        # Recent tickets
        recent_query = db.query(ticket_history).filter(
            ticket_history.c.project_jira_id == project_jira_id
        ).order_by(
            ticket_history.c.created_at.desc()
        ).limit(10).all()

        recent_tickets = []
        for ticket in recent_query:
            assigned_to_name = None
            if ticket.assigned_to_id:
                member = db.execute(
                    team_members.select().where(team_members.c.id == ticket.assigned_to_id)
                ).first()
                if member:
                    assigned_to_name = member.name

            recent_tickets.append(ProjectRecentTicket(
                ticket_id=ticket.id,
                redmine_id=ticket.redmine_ticket_id,
                subject=ticket.subject or f"Ticket {ticket.redmine_ticket_id}",
                status=ticket.status,
                priority=ticket.priority or "normal",
                assigned_to=assigned_to_name,
                created_at=ticket.created_at
            ))

        # Trend data (last 30 days)
        trend_data = []
        for i in range(30):
            day = datetime.now() - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")

            created_count = db.query(func.count(ticket_history.c.id)).filter(
                ticket_history.c.project_jira_id == project_jira_id,
                func.date(ticket_history.c.created_at) == day.date()
            ).scalar() or 0

            resolved_count = db.query(func.count(ticket_history.c.id)).filter(
                ticket_history.c.project_jira_id == project_jira_id,
                func.date(ticket_history.c.resolved_at) == day.date()
            ).scalar() or 0

            trend_data.append(ProjectTrendPoint(
                date=day_str,
                created=created_count,
                resolved=resolved_count
            ))

        trend_data.reverse()

        # Calculate SLA compliance
        resolved_tickets = summary_query.resolved_tickets or 0
        resolved_on_time = summary_query.resolved_on_time or 0
        compliance_rate = (resolved_on_time / resolved_tickets) * 100 if resolved_tickets else 100.0

        detail = ProjectDetail(
            project_jira_id=project_jira_id,
            total_tickets=summary_query.total_tickets or 0,
            open_tickets=summary_query.open_tickets or 0,
            resolved_tickets=resolved_tickets,
            breached_tickets=summary_query.breached_tickets or 0,
            sla_compliance_rate=round(compliance_rate, 2),
            active_engineers=summary_query.active_engineers or 0,
            last_activity=summary_query.last_activity,
            status_breakdown=status_breakdown,
            priority_breakdown=priority_breakdown,
            team_contributors=team_contributors,
            recent_tickets=recent_tickets,
            trend_data=trend_data,
            ai_insights=None  # Could add AI insights in future
        )

        logger.info(f"✅ Retrieved project detail for {project_jira_id}")

        return ProjectDetailResponse(project=detail)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get project detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
