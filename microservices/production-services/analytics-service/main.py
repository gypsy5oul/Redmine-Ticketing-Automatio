#!/usr/bin/env python3
"""
Analytics & ML Service - ML predictions, forecasting, dashboards

Port: 8006
Complete implementation with all endpoints from monolithic backend
"""

import os
import enum
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy import func, desc, and_, case, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
from loguru import logger

# ============================================================================
# SETTINGS
# ============================================================================

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    SERVICE_NAME: str = "analytics-service"
    SERVICE_PORT: int = 8006

settings = Settings()

# ============================================================================
# DATABASE
# ============================================================================

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# ENUMS
# ============================================================================

class TicketStatus(str, enum.Enum):
    """Ticket status"""
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"

class TicketPriority(str, enum.Enum):
    """Ticket priorities"""
    P1_CRITICAL = "P1(Critical)"
    P2_HIGH = "P2(High)"
    P3_MEDIUM = "P3(Medium)"
    P4_LOW = "P4(Low)"
    P5_TRIVIAL = "P5(Trivial)"

class SLAStatus(str, enum.Enum):
    """SLA status"""
    WITHIN_SLA = "within_sla"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    BREACHED = "breached"

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

# ============================================================================
# MODELS
# ============================================================================

class TicketHistory(Base):
    """Complete ticket lifecycle tracking"""
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    redmine_ticket_id = Column(Integer, unique=True, nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    description = Column(Text)
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    priority = Column(SQLEnum(TicketPriority), nullable=False, index=True)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.NEW, index=True)
    sla_breached = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), index=True)
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))

class TeamMember(Base):
    """Team member information"""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    redmine_user_id = Column(Integer)
    active = Column(Boolean, default=True)
    max_tickets = Column(Integer, default=5)
    team_level = Column(String(10))
    total_tickets_resolved = Column(Integer, default=0)
    sla_compliance_rate = Column(Float, default=100.0)
    avg_resolution_time_hours = Column(Float, default=0.0)

class SLATracker(Base):
    """Real-time SLA tracking for each ticket"""
    __tablename__ = "sla_trackers"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), unique=True, index=True)
    status = Column(SQLEnum(SLAStatus), default=SLAStatus.WITHIN_SLA, index=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))

class TicketCollaboration(Base):
    """Track multiple engineers collaborating on tickets"""
    __tablename__ = "ticket_collaborations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"))
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime(timezone=True))

class Activity(Base):
    """Activity log for real-time feed"""
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(SQLEnum(ActivityType), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="SET NULL"), index=True)
    user_id = Column(Integer, ForeignKey("team_members.id", ondelete="SET NULL"))
    icon = Column(String(50))
    color = Column(String(20))
    created_at = Column(DateTime, nullable=False, index=True)

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Analytics & ML Service",
    version="1.0.0",
    description="Dashboard metrics, analytics, and ML predictions"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _session_type_to_str(value):
    """Convert enum to string"""
    if value is None:
        return None
    if hasattr(value, 'value'):
        return value.value
    return str(value)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Starting {settings.SERVICE_NAME}")

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

# ============================================================================
# DASHBOARD ENDPOINTS
# ============================================================================

@app.get("/api/v1/dashboard/metrics", tags=["Dashboard"])
async def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Get comprehensive dashboard metrics

    Returns summary of:
    - Total tickets (by status)
    - SLA compliance rate
    - Team workload
    - Recent activity
    """
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        # Total tickets by status
        total_tickets = db.query(TicketHistory).count()
        open_tickets = db.query(TicketHistory).filter(
            TicketHistory.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        resolved_today = db.query(TicketHistory).filter(
            TicketHistory.resolved_at >= today_start
        ).count()

        # SLA metrics
        total_resolved = db.query(TicketHistory).filter(
            TicketHistory.resolved_at.isnot(None)
        ).count()
        sla_breached = db.query(TicketHistory).filter(
            TicketHistory.sla_breached == True
        ).count()
        sla_compliance_rate = ((total_resolved - sla_breached) / total_resolved * 100) if total_resolved > 0 else 100

        # Team metrics
        active_members = db.query(TeamMember).filter(TeamMember.active == True).count()

        # Avg resolution time (last 7 days)
        resolved_last_week = db.query(TicketHistory).filter(
            and_(
                TicketHistory.resolved_at >= week_ago,
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.created_at.isnot(None)
            )
        ).all()

        if resolved_last_week:
            resolution_times = [
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved_last_week
                if t.resolved_at and t.created_at
            ]
            avg_resolution_hours = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        else:
            avg_resolution_hours = 0

        # Count at-risk and critical tickets
        at_risk_count = db.query(SLATracker).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL])
        ).count()

        critical_count = db.query(TicketHistory).filter(
            TicketHistory.priority == TicketPriority.P1_CRITICAL,
            TicketHistory.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()

        # Calculate team capacity
        total_capacity = db.query(func.sum(TeamMember.max_tickets)).filter(
            TeamMember.active == True
        ).scalar() or 0

        team_capacity_percentage = round((open_tickets / total_capacity * 100) if total_capacity > 0 else 0, 1)

        # Count active collaborations
        active_collaborations = db.query(func.count(func.distinct(TicketCollaboration.ticket_id))).filter(
            TicketCollaboration.is_active == True
        ).scalar() or 0

        # Build 7-day window for trend insights
        day_windows = [today_start - timedelta(days=i) for i in range(6, -1, -1)]

        # Daily ticket creation trend (sparkline for Total Tickets)
        tickets_created_rows = (
            db.query(
                func.date_trunc('day', TicketHistory.created_at).label('day_bucket'),
                func.count(TicketHistory.id).label('count')
            )
            .filter(TicketHistory.created_at >= week_ago)
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        tickets_created_map = {
            (row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket): int(row.count)
            for row in tickets_created_rows
        }
        tickets_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": tickets_created_map.get(day.date(), 0)
            }
            for day in day_windows
        ]

        # SLA compliance trend (daily compliance rate)
        sla_trend_rows = (
            db.query(
                func.date_trunc('day', TicketHistory.resolved_at).label('day_bucket'),
                func.count(TicketHistory.id).label('resolved'),
                func.sum(
                    case((TicketHistory.sla_breached == False, 1), else_=0)
                ).label('within')
            )
            .filter(
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.resolved_at >= week_ago
            )
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        sla_trend_map = {}
        for row in sla_trend_rows:
            day_key = row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket
            resolved = int(row.resolved or 0)
            within = int(row.within or 0)
            rate = (within / resolved * 100) if resolved > 0 else 100.0
            sla_trend_map[day_key] = round(rate, 1)
        sla_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": sla_trend_map.get(day.date(), 100.0)
            }
            for day in day_windows
        ]

        # At risk / critical trend
        status_timestamp = func.coalesce(SLATracker.updated_at, SLATracker.created_at)
        at_risk_rows = (
            db.query(
                func.date_trunc('day', status_timestamp).label('day_bucket'),
                func.sum(case((SLATracker.status == SLAStatus.AT_RISK, 1), else_=0)).label('at_risk'),
                func.sum(case((SLATracker.status == SLAStatus.CRITICAL, 1), else_=0)).label('critical')
            )
            .filter(status_timestamp >= week_ago)
            .group_by('day_bucket')
            .order_by('day_bucket')
            .all()
        )
        at_risk_map = {}
        for row in at_risk_rows:
            day_key = row.day_bucket.date() if hasattr(row.day_bucket, 'date') else row.day_bucket
            at_risk_map[day_key] = int(row.at_risk or 0) + int(row.critical or 0)
        at_risk_sparkline = [
            {
                "label": day.strftime('%b %d'),
                "value": at_risk_map.get(day.date(), 0)
            }
            for day in day_windows
        ]

        # Team capacity usage trend (open tickets vs capacity)
        open_statuses = [TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]
        capacity_sparkline = []
        for day_start in day_windows:
            day_end = day_start + timedelta(days=1)
            open_count = (
                db.query(func.count(TicketHistory.id))
                .filter(
                    TicketHistory.status.in_(open_statuses),
                    TicketHistory.created_at <= day_end,
                    or_(TicketHistory.resolved_at.is_(None), TicketHistory.resolved_at > day_start)
                )
                .scalar()
            ) or 0
            utilization = round((open_count / total_capacity * 100), 1) if total_capacity > 0 else 0
            capacity_sparkline.append(
                {
                    "label": day_start.strftime('%b %d'),
                    "value": utilization
                }
            )

        # Priority distribution for tickets created today
        priority_rows = (
            db.query(
                TicketHistory.priority,
                func.count(TicketHistory.id).label('count')
            )
            .filter(TicketHistory.created_at >= today_start)
            .group_by(TicketHistory.priority)
            .all()
        )
        priority_distribution = [
            {
                "label": priority.value if hasattr(priority, 'value') else str(priority),
                "value": int(row_count)
            }
            for priority, row_count in priority_rows
        ]

        # SLA status distribution for all trackers
        sla_distribution_rows = (
            db.query(
                SLATracker.status,
                func.count(SLATracker.id).label('count')
            )
            .group_by(SLATracker.status)
            .all()
        )
        sla_distribution = [
            {"label": status.value if hasattr(status, 'value') else str(status), "value": int(count)}
            for status, count in sla_distribution_rows
        ]

        # Capacity distribution across active team
        metrics_in_progress = open_tickets
        used_capacity = min(metrics_in_progress, total_capacity)
        remaining_capacity = max(total_capacity - used_capacity, 0)
        overflow_capacity = max(metrics_in_progress - total_capacity, 0)
        capacity_distribution = [
            {"label": "Active Load", "value": used_capacity}
        ]
        if remaining_capacity > 0:
            capacity_distribution.append({"label": "Available", "value": remaining_capacity})
        if overflow_capacity > 0:
            capacity_distribution.append({"label": "Overflow", "value": overflow_capacity})

        # At risk distribution (derived from SLA distribution)
        at_risk_distribution = []
        distribution_lookup = {item["label"]: item["value"] for item in sla_distribution}
        at_risk_distribution.append({"label": "At Risk", "value": distribution_lookup.get(SLAStatus.AT_RISK.value, 0)})
        at_risk_distribution.append({"label": "Critical", "value": distribution_lookup.get(SLAStatus.CRITICAL.value, 0)})
        safe_value = distribution_lookup.get(SLAStatus.WITHIN_SLA.value, 0)
        if safe_value:
            at_risk_distribution.append({"label": "Within SLA", "value": safe_value})

        card_insights = {
            "total_tickets": {
                "sparkline": tickets_sparkline,
                "distribution": priority_distribution,
            },
            "sla_compliance": {
                "sparkline": sla_sparkline,
                "distribution": sla_distribution,
            },
            "at_risk": {
                "sparkline": at_risk_sparkline,
                "distribution": at_risk_distribution,
            },
            "team_capacity": {
                "sparkline": capacity_sparkline,
                "distribution": capacity_distribution,
            },
        }

        return {
            "total_tickets_today": resolved_today,
            "tickets_in_progress": open_tickets,
            "sla_compliance_rate": round(sla_compliance_rate, 1),
            "avg_resolution_time_hours": round(avg_resolution_hours, 1),
            "at_risk_tickets": at_risk_count,
            "critical_tickets": critical_count,
            "team_capacity_percentage": team_capacity_percentage,
            "active_collaborations": active_collaborations,
            "card_insights": card_insights
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch dashboard metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/dashboard/activity", tags=["Dashboard"])
async def get_recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    """Get recent ticket activity"""
    try:
        activities = (
            db.query(Activity)
            .order_by(desc(Activity.created_at))
            .limit(limit)
            .all()
        )

        activity_data = []
        for activity in activities:
            # Fetch ticket info if ticket_id exists
            ticket_info = None
            if activity.ticket_id:
                ticket = db.query(TicketHistory).filter(TicketHistory.id == activity.ticket_id).first()
                if ticket:
                    ticket_info = {
                        "id": ticket.redmine_ticket_id,
                        "subject": ticket.subject,
                        "status": _session_type_to_str(ticket.status),
                        "priority": _session_type_to_str(ticket.priority)
                    }

            activity_data.append({
                "id": activity.id,
                "type": _session_type_to_str(activity.activity_type),
                "title": activity.title,
                "description": activity.description,
                "ticket": ticket_info,
                "icon": activity.icon,
                "color": activity.color,
                "created_at": activity.created_at.isoformat() if activity.created_at else None
            })

        return {
            "activities": activity_data,
            "count": len(activity_data)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch recent activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@app.get("/api/v1/analytics/dashboard", tags=["Analytics"])
async def get_dashboard_simple(db: Session = Depends(get_db)):
    """Get simple dashboard metrics (legacy endpoint)"""
    try:
        total_tickets = db.query(TicketHistory).count()
        open_tickets = db.query(TicketHistory).filter(
            TicketHistory.status.in_([TicketStatus.NEW, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()
        sla_breached = db.query(TicketHistory).filter(TicketHistory.sla_breached == True).count()

        resolved = db.query(TicketHistory).filter(
            TicketHistory.resolved_at.isnot(None),
            TicketHistory.created_at.isnot(None)
        ).all()

        if resolved:
            total_hours = sum(
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved
                if t.resolved_at and t.created_at
            )
            avg_resolution_hours = total_hours / len(resolved)
        else:
            avg_resolution_hours = 0.0

        return {
            "success": True,
            "metrics": {
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "resolved_tickets": len(resolved),
                "sla_breached": sla_breached,
                "sla_compliance_rate": round(((total_tickets - sla_breached) / total_tickets * 100), 2) if total_tickets > 0 else 100.0,
                "avg_resolution_hours": round(avg_resolution_hours, 2)
            }
        }
    except Exception as e:
        logger.error(f"❌ Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
