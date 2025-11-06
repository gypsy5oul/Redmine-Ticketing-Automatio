#!/usr/bin/env python3
"""
Analytics & ML Service - ML predictions, forecasting, dashboards

Port: 8006
Complete implementation with all endpoints from monolithic backend
"""

import os
import sys
import enum
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy import func, desc, and_, case, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship
import redis

# Add shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from shared.auth_utils import setup_logging, log_request, get_current_user, User

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
# REDIS CACHE
# ============================================================================

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5
)

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

# Setup enhanced logging
logger = setup_logging("analytics-service", os.getenv("LOG_LEVEL", "INFO"))

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
async def get_dashboard_metrics(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard metrics - Requires: Any authenticated user

    Returns summary of:
    - Total tickets (by status)
    - SLA compliance rate
    - Team workload
    - Recent activity
    """
    log_request(logger, request, user.id, "GET /api/v1/dashboard/metrics")
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
async def get_recent_activity(
    user: User = Depends(get_current_user),
    request: Request = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent ticket activity - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/dashboard/activity")
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
async def get_dashboard_simple(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get simple dashboard metrics (legacy endpoint) - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/analytics/dashboard")
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


# ============================================================================
# ML PREDICTION ENDPOINTS (Phase 1B)
# ============================================================================

class SimpleLLMPredictor:
    """Simplified ML predictor using rule-based fallback logic"""

    @staticmethod
    def predict_category(ticket: dict) -> dict:
        """Predict ticket category using keyword matching"""
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()
        text = f"{subject} {description}"

        # Simple keyword matching
        if any(kw in text for kw in ['kubernetes', 'k8s', 'pod', 'deployment', 'helm']):
            category = 'kubernetes'
        elif any(kw in text for kw in ['database', 'postgres', 'mysql', 'sql', 'mongodb']):
            category = 'database'
        elif any(kw in text for kw in ['cicd', 'ci/cd', 'pipeline', 'gitlab', 'jenkins', 'github']):
            category = 'cicd'
        elif any(kw in text for kw in ['network', 'firewall', 'dns', 'routing', 'vpn']):
            category = 'network'
        elif any(kw in text for kw in ['rabbitmq', 'kafka', 'redis', 'messaging', 'queue']):
            category = 'messaging'
        elif any(kw in text for kw in ['docker', 'container', 'image']):
            category = 'container'
        else:
            category = 'application'

        return {
            "category": category,
            "confidence": 0.65,
            "probabilities": {category: 0.65},
            "method": "rule_based"
        }

    @staticmethod
    def predict_complexity(ticket: dict) -> dict:
        """Predict ticket complexity based on priority and keywords"""
        priority = ticket.get('priority', 'P3(Medium)')
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()
        text = f"{subject} {description}"

        # Check for complexity indicators in text
        complex_keywords = ['migration', 'upgrade', 'architecture', 'redesign', 'refactor']
        critical_keywords = ['outage', 'down', 'critical', 'emergency', 'urgent']
        simple_keywords = ['typo', 'minor', 'cosmetic', 'documentation', 'config']

        # Base complexity on priority
        if priority == 'P1(Critical)' or any(kw in text for kw in critical_keywords):
            complexity = 'critical'
            confidence = 0.75
        elif priority == 'P2(High)' or any(kw in text for kw in complex_keywords):
            complexity = 'complex'
            confidence = 0.70
        elif any(kw in text for kw in simple_keywords):
            complexity = 'simple'
            confidence = 0.65
        else:
            complexity = 'moderate'
            confidence = 0.60

        return {
            "complexity": complexity,
            "confidence": confidence,
            "probabilities": {complexity: confidence},
            "method": "rule_based"
        }

    @staticmethod
    def predict_resolution_time(ticket: dict) -> dict:
        """Predict resolution time based on priority and complexity"""
        priority = ticket.get('priority', 'P3(Medium)')
        subject = ticket.get('subject', '').lower()
        description = ticket.get('description', '').lower()
        text = f"{subject} {description}"

        # Base estimation on priority
        priority_hours = {
            'P1(Critical)': 2.0,
            'P2(High)': 4.0,
            'P3(Medium)': 8.0,
            'P4(Low)': 16.0,
            'P5(Trivial)': 24.0
        }

        base_hours = priority_hours.get(priority, 8.0)

        # Adjust based on complexity indicators
        if any(kw in text for kw in ['migration', 'upgrade', 'architecture']):
            estimated_hours = base_hours * 1.5
        elif any(kw in text for kw in ['typo', 'minor', 'config']):
            estimated_hours = base_hours * 0.5
        else:
            estimated_hours = base_hours

        return {
            "estimated_hours": round(estimated_hours, 1),
            "confidence": 0.60,
            "method": "rule_based",
            "priority_based": True
        }


@app.post("/api/v1/ml/predict/category", tags=["Analytics", "ML"])
async def predict_ticket_category(
    user: User = Depends(get_current_user),
    request: Request = None,
    subject: str = None,
    description: str = "",
    priority: str = "P3(Medium)"
):
    """
    Predict ticket category using ML/rule-based logic - Requires: Any authenticated user

    Source: /backend/app/main.py:1819-1844

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (optional)

    Returns:
        {
            "category": str,
            "confidence": float,
            "probabilities": dict,
            "method": str
        }
    """
    log_request(logger, request, user.id, "POST /api/v1/ml/predict/category")
    try:
        ticket = {
            "subject": subject,
            "description": description,
            "priority": priority
        }

        predictor = SimpleLLMPredictor()
        result = predictor.predict_category(ticket)

        logger.info(f"✅ Category prediction: {result['category']} (confidence: {result['confidence']})")

        return result

    except Exception as e:
        logger.error(f"❌ Category prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ml/predict/complexity", tags=["Analytics", "ML"])
async def predict_ticket_complexity(
    user: User = Depends(get_current_user),
    request: Request = None,
    subject: str = None,
    description: str = "",
    priority: str = "P3(Medium)"
):
    """
    Predict ticket complexity using ML/rule-based logic - Requires: Any authenticated user

    Source: /backend/app/main.py:1846-1872

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (optional)

    Returns:
        {
            "complexity": str,
            "confidence": float,
            "probabilities": dict,
            "method": str
        }
    """
    log_request(logger, request, user.id, "POST /api/v1/ml/predict/complexity")
    try:
        ticket = {
            "subject": subject,
            "description": description,
            "priority": priority
        }

        predictor = SimpleLLMPredictor()
        result = predictor.predict_complexity(ticket)

        logger.info(f"✅ Complexity prediction: {result['complexity']} (confidence: {result['confidence']})")

        return result

    except Exception as e:
        logger.error(f"❌ Complexity prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ml/predict/resolution-time", tags=["Analytics", "ML"])
async def predict_resolution_time(
    user: User = Depends(get_current_user),
    request: Request = None,
    subject: str = None,
    description: str = "",
    priority: str = "P3(Medium)"
):
    """
    Predict ticket resolution time using ML/rule-based logic - Requires: Any authenticated user

    Source: /backend/app/main.py:1875-1900

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (optional)

    Returns:
        {
            "estimated_hours": float,
            "confidence": float,
            "method": str
        }
    """
    log_request(logger, request, user.id, "POST /api/v1/ml/predict/resolution-time")
    try:
        ticket = {
            "subject": subject,
            "description": description,
            "priority": priority
        }

        predictor = SimpleLLMPredictor()
        result = predictor.predict_resolution_time(ticket)

        logger.info(f"✅ Resolution time prediction: {result['estimated_hours']} hours (confidence: {result['confidence']})")

        return result

    except Exception as e:
        logger.error(f"❌ Resolution time prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ml/predict/all", tags=["Analytics", "ML"])
async def predict_all_ticket_attributes(
    user: User = Depends(get_current_user),
    request: Request = None,
    subject: str = None,
    description: str = "",
    priority: str = "P3(Medium)"
):
    """
    Run all ML predictions at once for a ticket - Requires: Any authenticated user

    Source: /backend/app/main.py:1903-1947

    Args:
        subject: Ticket subject line
        description: Ticket description (optional)
        priority: Ticket priority (optional)

    Returns:
        {
            "category": {...},
            "complexity": {...},
            "resolution_time": {...},
            "ticket_summary": {...}
        }
    """
    log_request(logger, request, user.id, "POST /api/v1/ml/predict/all")
    try:
        ticket = {
            "subject": subject,
            "description": description,
            "priority": priority
        }

        predictor = SimpleLLMPredictor()

        # Run all predictions
        category = predictor.predict_category(ticket)
        complexity = predictor.predict_complexity(ticket)
        resolution = predictor.predict_resolution_time(ticket)

        # Calculate average confidence
        avg_confidence = round((
            category.get("confidence", 0.5) +
            complexity.get("confidence", 0.5) +
            resolution.get("confidence", 0.5)
        ) / 3, 2)

        result = {
            "category": category,
            "complexity": complexity,
            "resolution_time": resolution,
            "ticket_summary": {
                "subject": subject,
                "predicted_category": category["category"],
                "predicted_complexity": complexity["complexity"],
                "predicted_hours": resolution["estimated_hours"],
                "avg_confidence": avg_confidence
            }
        }

        logger.info(
            f"✅ All predictions complete: "
            f"category={category['category']}, "
            f"complexity={complexity['complexity']}, "
            f"hours={resolution['estimated_hours']}"
        )

        return result

    except Exception as e:
        logger.error(f"❌ Combined prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ANALYTICS ENDPOINTS (Phase 1C)
# ============================================================================

@app.get("/api/v1/analytics/forecast", tags=["Analytics"])
async def get_volume_forecast(
    user: User = Depends(get_current_user),
    request: Request = None,
    days: int = Query(7, description="Number of days to forecast"),
    db: Session = Depends(get_db)
):
    """
    Get ticket volume forecast for capacity planning - Requires: Any authenticated user

    Source: /backend/app/main.py:1665-1673

    Args:
        days: Number of days to forecast (default: 7)

    Returns:
        {
            "historical": [...],
            "forecast": [...],
            "busy_periods": [...],
            "historical_avg": int,
            "trend": str,
            "recommendations": {...}
        }
    """
    log_request(logger, request, user.id, "GET /api/v1/analytics/forecast")
    try:
        now = datetime.now()
        end_date = now
        start_date = now - timedelta(days=90)  # Last 90 days

        # Get historical daily volumes
        from sqlalchemy import func, Date

        daily_volumes = (
            db.query(
                func.date(TicketHistory.created_at).label('date'),
                func.count(TicketHistory.id).label('count')
            )
            .filter(TicketHistory.created_at >= start_date)
            .group_by(func.date(TicketHistory.created_at))
            .order_by(func.date(TicketHistory.created_at))
            .all()
        )

        if len(daily_volumes) < 14:
            return {
                "forecast": [],
                "busy_periods": [],
                "recommendations": {"note": "Need at least 14 days of data for forecasting"},
                "historical_avg": 0,
                "trend": "unknown"
            }

        # Convert to arrays for calculations
        import numpy as np
        dates = [row[0] for row in daily_volumes]
        volumes = np.array([row[1] for row in daily_volumes])

        # Calculate statistics
        avg_volume = float(np.mean(volumes))
        std_volume = float(np.std(volumes))

        # Simple trend detection (last 7 days vs previous 7 days)
        if len(volumes) >= 14:
            recent_avg = np.mean(volumes[-7:])
            prev_avg = np.mean(volumes[-14:-7])
            trend_diff = recent_avg - prev_avg

            if trend_diff > 2:
                trend = "increasing"
            elif trend_diff < -2:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Simple moving average forecast
        window_size = min(7, len(volumes))
        ma = np.mean(volumes[-window_size:])

        forecast = []
        for i in range(days):
            pred_date = end_date + timedelta(days=i+1)
            predicted = int(ma)

            forecast.append({
                "date": pred_date.strftime("%Y-%m-%d"),
                "count": predicted,
                "predicted": True,
                "lower_bound": max(0, int(predicted - std_volume)),
                "upper_bound": int(predicted + std_volume),
                "confidence": 0.70
            })

        # Historical data
        historical = [
            {
                "date": date.strftime("%Y-%m-%d") if hasattr(date, 'strftime') else str(date),
                "count": int(count),
                "predicted": False
            }
            for date, count in zip(dates, volumes)
        ]

        # Identify busy periods (above avg + 1 std)
        busy_threshold = avg_volume + std_volume
        busy_periods = [f for f in forecast if f['count'] > busy_threshold]

        # Get current capacity
        current_capacity = db.query(TeamMember).filter(
            TeamMember.active == True
        ).count() * 8

        # Generate recommendations
        recommendations = {}
        max_predicted = max(f['count'] for f in forecast) if forecast else 0

        if max_predicted > current_capacity * 0.8:
            recommendations['capacity_alert'] = (
                f"Peak volume ({max_predicted}) may exceed 80% capacity. "
                f"Consider on-call resources."
            )

        if trend == "increasing":
            recommendations['trend_alert'] = (
                f"Ticket volume is trending upward. Monitor capacity."
            )

        if len(busy_periods) >= 3:
            recommendations['busy_period_alert'] = (
                f"{len(busy_periods)} busy days forecasted. Ensure adequate staffing."
            )

        logger.info(f"✅ Forecast generated: {days} days, trend={trend}, avg={avg_volume:.1f}")

        return {
            "historical": historical,
            "forecast": forecast,
            "busy_periods": busy_periods,
            "historical_avg": int(avg_volume),
            "historical_std": round(std_volume, 2),
            "trend": trend,
            "current_capacity": current_capacity,
            "recommendations": recommendations,
            "method": "moving_average"
        }

    except Exception as e:
        logger.error(f"❌ Forecast generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/sla-prediction/{ticket_id}", tags=["Analytics"])
async def predict_sla_breach(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Predict SLA breach probability for a ticket - Requires: Any authenticated user

    Source: /backend/app/main.py:1676-1692

    Args:
        ticket_id: Database ticket ID (not redmine_ticket_id)

    Returns:
        {
            "probability": 0.0-1.0,
            "risk_level": "low|medium|high",
            "risk_factors": [...],
            "recommendation": str
        }
    """
    log_request(logger, request, user.id, f"GET /api/v1/analytics/sla-prediction/{ticket_id}")
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if not ticket.assigned_to_id:
            return {
                "probability": 0.5,
                "risk_level": "medium",
                "risk_factors": ["Ticket not assigned yet"],
                "recommendation": "Assign ticket to assess SLA risk"
            }

        # Calculate risk factors
        factors = []
        risk_score = 0.0

        # Priority factor
        if ticket.priority == TicketPriority.P1_CRITICAL:
            risk_score += 0.3
            factors.append("Critical priority")
        elif ticket.priority == TicketPriority.P2_HIGH:
            risk_score += 0.15
            factors.append("High priority")

        # Check assignee workload
        assignee = db.query(TeamMember).filter(TeamMember.id == ticket.assigned_to_id).first()
        if assignee:
            current_tickets = db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == assignee.id,
                TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
            ).count()

            if current_tickets >= assignee.max_tickets * 0.8:
                risk_score += 0.2
                factors.append("High assignee workload")

            # Historical performance
            if assignee.sla_compliance_rate < 85:
                risk_score += 0.2
                factors.append("Below average SLA compliance")

        # Time since creation
        if ticket.created_at:
            hours_open = (datetime.now() - ticket.created_at).total_seconds() / 3600

            # Check against SLA target (simplified)
            sla_hours = {
                TicketPriority.P1_CRITICAL: 4,
                TicketPriority.P2_HIGH: 8,
                TicketPriority.P3_MEDIUM: 24,
                TicketPriority.P4_LOW: 48,
                TicketPriority.P5_TRIVIAL: 72
            }
            target_hours = sla_hours.get(ticket.priority, 24)

            if hours_open > target_hours * 0.7:
                risk_score += 0.3
                factors.append(f"Already open {hours_open:.1f} hours (target: {target_hours}h)")

        # Determine risk level
        if risk_score >= 0.7:
            risk_level = "high"
            recommendation = "Consider escalation or additional resources"
        elif risk_score >= 0.4:
            risk_level = "medium"
            recommendation = "Monitor closely, may need support"
        else:
            risk_level = "low"
            recommendation = "Normal processing expected"

        if not factors:
            factors.append("No significant risk factors identified")

        logger.info(f"✅ SLA prediction for ticket {ticket_id}: {risk_level} ({risk_score:.2f})")

        return {
            "probability": min(risk_score, 1.0),
            "risk_level": risk_level,
            "risk_factors": factors,
            "recommendation": recommendation,
            "ticket_id": ticket_id,
            "hours_open": round((datetime.now() - ticket.created_at).total_seconds() / 3600, 1) if ticket.created_at else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ SLA prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/ml/train", tags=["Analytics", "ML"])
async def train_ml_models(
    user: User = Depends(get_current_user),
    request: Request = None,
    force_retrain: bool = False,
    db: Session = Depends(get_db)
):
    """
    Train ML models with historical data - Requires: Any authenticated user

    Source: /backend/app/main.py:1695-1713

    This endpoint trains:
    - Category classifier
    - Complexity predictor
    - Resolution time predictor

    Requires at least 100 resolved tickets in database.

    Note: Currently returns stub since sklearn is not installed
    """
    log_request(logger, request, user.id, "POST /api/v1/ml/train")
    try:
        # Check training data availability
        total_tickets = db.query(TicketHistory).filter(
            TicketHistory.resolved_at.isnot(None)
        ).count()

        if total_tickets < 100:
            logger.warning(f"⚠️ Insufficient training data: {total_tickets} < 100")
            return {
                "success": False,
                "error": f"Need at least 100 resolved tickets for training",
                "current_count": total_tickets,
                "status": "insufficient_data"
            }

        logger.info(f"📊 ML training requested with {total_tickets} resolved tickets")

        # Return stub response - full implementation requires sklearn
        return {
            "success": True,
            "status": "using_rule_based",
            "message": "ML training not implemented - using rule-based predictions",
            "training_samples": total_tickets,
            "models_trained": 0,
            "rule_based_fallback": True,
            "trained_at": datetime.now().isoformat(),
            "note": "Install sklearn for full ML training support"
        }

    except Exception as e:
        logger.error(f"❌ ML training failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/team-performance", tags=["Analytics"])
async def get_team_performance(
    user: User = Depends(get_current_user),
    request: Request = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get team performance metrics - Requires: Any authenticated user

    Source: /backend/app/main.py:1716-1780

    Args:
        start_date: ISO format date (default: 30 days ago)
        end_date: ISO format date (default: today)

    Returns:
        {
            "performance": [...],
            "start_date": str,
            "end_date": str,
            "total_members": int
        }
    """
    log_request(logger, request, user.id, "GET /api/v1/analytics/team-performance")
    try:
        # Default to last 30 days
        if not end_date:
            end_dt = datetime.now()
        else:
            end_dt = datetime.fromisoformat(end_date)

        if not start_date:
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = datetime.fromisoformat(start_date)

        # Get all team members
        members = db.query(TeamMember).filter(TeamMember.active == True).all()

        performance_data = []

        for member in members:
            # Get tickets resolved by this member in date range
            resolved_tickets = db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == member.id,
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.resolved_at >= start_dt,
                TicketHistory.resolved_at <= end_dt
            ).all()

            tickets_resolved = len(resolved_tickets)

            # Calculate average resolution time
            if resolved_tickets:
                resolution_times = [
                    t.actual_resolution_hours for t in resolved_tickets
                    if t.actual_resolution_hours
                ]
                avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0

                # Calculate SLA compliance
                sla_met = sum(1 for t in resolved_tickets if not t.sla_breached)
                sla_rate = (sla_met / tickets_resolved * 100) if tickets_resolved > 0 else 100
            else:
                avg_resolution = member.avg_resolution_time_hours or 0
                sla_rate = member.sla_compliance_rate or 100

            performance_data.append({
                "member_id": member.id,
                "member_name": member.name,
                "team_level": _session_type_to_str(member.team_level) if member.team_level else "L1",
                "tickets_resolved": tickets_resolved,
                "avg_resolution_time": round(avg_resolution, 2),
                "sla_compliance_rate": round(sla_rate, 2),
                "active": member.active,
                "total_capacity": member.max_tickets
            })

        logger.info(f"✅ Team performance: {len(performance_data)} members, {start_dt.date()} to {end_dt.date()}")

        return {
            "performance": performance_data,
            "start_date": start_dt.date().isoformat(),
            "end_date": end_dt.date().isoformat(),
            "total_members": len(performance_data)
        }

    except Exception as e:
        logger.error(f"❌ Team performance fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ml/models/status", tags=["Analytics", "ML"])
async def get_ml_models_status(
    user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Get status of ML models (loaded, last trained, etc.) - Requires: Any authenticated user

    Source: /backend/app/main.py:1783-1816

    Returns:
        {
            "models": {...},
            "models_path": str,
            "all_present": bool,
            "status": str
        }
    """
    log_request(logger, request, user.id, "GET /api/v1/ml/models/status")
    try:
        # Check if ML models directory exists
        models_path = "/app/ml_models"  # Standard path
        models = [
            "category_classifier.joblib",
            "category_vectorizer.joblib",
            "complexity_classifier.joblib",
            "complexity_vectorizer.joblib",
            "resolution_regressor.joblib",
            "resolution_vectorizer.joblib"
        ]

        models_status = {}

        import os
        for model in models:
            path = f"{models_path}/{model}"
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                models_status[model] = {
                    "exists": True,
                    "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                    "size_kb": round(os.path.getsize(path) / 1024, 2)
                }
            else:
                models_status[model] = {"exists": False}

        all_present = all(m["exists"] for m in models_status.values())

        logger.info(f"✅ ML models status: {sum(1 for m in models_status.values() if m['exists'])}/{len(models)} present")

        return {
            "models": models_status,
            "models_path": models_path,
            "all_present": all_present,
            "status": "trained" if all_present else "using_rule_based",
            "prediction_method": "ml" if all_present else "rule_based",
            "note": "Using rule-based predictions - train models with POST /api/v1/ml/train"
        }

    except Exception as e:
        logger.error(f"❌ Model status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ACTIVITIES/AUDIT LOG ENDPOINTS (Phase 3)
# ============================================================================

@app.get("/api/v1/activities", tags=["Activities"])
async def get_activities(
    user: User = Depends(get_current_user),
    request: Request = None,
    limit: int = Query(50, description="Maximum number of activities"),
    hours: int = Query(24, description="Get activities from last N hours"),
    db: Session = Depends(get_db)
):
    """
    Get recent activities for real-time feed - Requires: Any authenticated user

    Source: /backend/app/main.py:2928-2958

    Args:
        limit: Maximum number of activities (default: 50)
        hours: Get activities from last N hours (default: 24)

    Returns:
        List of recent activities
    """
    log_request(logger, request, user.id, "GET /api/v1/activities")
    try:
        from_time = datetime.now() - timedelta(hours=hours)

        # Get recent activities
        activities = (
            db.query(Activity)
            .filter(Activity.created_at >= from_time)
            .order_by(desc(Activity.created_at))
            .limit(limit)
            .all()
        )

        # Format activities
        activity_list = []
        for activity in activities:
            # Get ticket details if associated
            ticket_info = None
            if activity.ticket_id:
                ticket = db.query(TicketHistory).filter(
                    TicketHistory.id == activity.ticket_id
                ).first()
                if ticket:
                    ticket_info = {
                        "id": ticket.id,
                        "redmine_ticket_id": ticket.redmine_ticket_id,
                        "subject": ticket.subject,
                        "status": _session_type_to_str(ticket.status),
                        "priority": _session_type_to_str(ticket.priority)
                    }

            activity_list.append({
                "id": activity.id,
                "type": _session_type_to_str(activity.activity_type),
                "title": activity.title,
                "description": activity.description,
                "ticket": ticket_info,
                "user_id": activity.user_id,
                "metadata": activity.metadata,
                "created_at": activity.created_at.isoformat()
            })

        logger.info(f"✅ Retrieved {len(activity_list)} activities from last {hours} hours")

        return {
            "success": True,
            "count": len(activity_list),
            "activities": activity_list,
            "timeframe_hours": hours
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/activities/ticket/{ticket_id}", tags=["Activities"])
async def get_ticket_activities(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    limit: int = Query(20, description="Maximum number of activities"),
    db: Session = Depends(get_db)
):
    """
    Get activities for a specific ticket - Requires: Any authenticated user

    Source: /backend/app/main.py:2961-2983

    Args:
        ticket_id: Ticket ID (database ID, not redmine_ticket_id)
        limit: Maximum number of activities (default: 20)

    Returns:
        List of activities for the ticket
    """
    log_request(logger, request, user.id, f"GET /api/v1/activities/ticket/{ticket_id}")
    try:
        # Verify ticket exists
        ticket = db.query(TicketHistory).filter(
            TicketHistory.id == ticket_id
        ).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Get activities for this ticket
        activities = (
            db.query(Activity)
            .filter(Activity.ticket_id == ticket_id)
            .order_by(desc(Activity.created_at))
            .limit(limit)
            .all()
        )

        # Format activities
        activity_list = []
        for activity in activities:
            activity_list.append({
                "id": activity.id,
                "type": _session_type_to_str(activity.activity_type),
                "title": activity.title,
                "description": activity.description,
                "user_id": activity.user_id,
                "metadata": activity.metadata,
                "created_at": activity.created_at.isoformat()
            })

        logger.info(f"✅ Retrieved {len(activity_list)} activities for ticket {ticket_id}")

        return {
            "success": True,
            "ticket_id": ticket_id,
            "ticket": {
                "id": ticket.id,
                "redmine_ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "status": _session_type_to_str(ticket.status)
            },
            "count": len(activity_list),
            "activities": activity_list
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch ticket activities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/api/v1/metrics/cache", tags=["Cache"])
async def get_cache_metrics(
    user: User = Depends(get_current_user),
    request: Request = None
):
    """
    Get comprehensive cache performance metrics - Requires: Any authenticated user

    Source: /backend/app/main.py:168-198

    Returns Redis cache statistics and metrics
    """
    log_request(logger, request, user.id, "GET /api/v1/metrics/cache")
    try:
        # Get Redis info
        try:
            redis_info = redis_client.info('memory')
            cache_size_mb = round(redis_info.get('used_memory', 0) / 1024 / 1024, 2)
            redis_keys = redis_client.dbsize()
            redis_connected = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            cache_size_mb = 0
            redis_keys = 0
            redis_connected = False

        logger.info(f"✅ Cache metrics retrieved: {cache_size_mb}MB, {redis_keys} keys")

        return {
            "redis": {
                "connected": redis_connected,
                "memory_mb": cache_size_mb,
                "total_keys": redis_keys,
                "max_memory": redis_info.get('maxmemory', 0) if redis_connected else 0,
                "eviction_policy": redis_info.get('maxmemory_policy', 'unknown') if redis_connected else 'unknown'
            },
            "cache_health": "healthy" if redis_connected else "disconnected",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Failed to get cache metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/cache/clear", tags=["Cache"])
async def clear_cache(
    user: User = Depends(get_current_user),
    request: Request = None,
    cache_type: str = Query("all", description="Type of cache to clear")
):
    """
    Clear cache by type - Requires: Any authenticated user

    Source: /backend/app/main.py:201-245

    Args:
        cache_type: Type of cache to clear (llm, query, sla, workload, analytics, all)
    """
    log_request(logger, request, user.id, f"DELETE /api/v1/cache/clear?cache_type={cache_type}")
    try:
        patterns = {
            "llm": "llm:cache:*",
            "query": "query:*",
            "sla": "sla:*",
            "workload": "workload:*",
            "analytics": "analytics:*",
            "collaborators": "collaborators:*",
            "dashboard": "dashboard:*",
            "all": "*"
        }

        if cache_type not in patterns:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cache_type. Must be one of: {list(patterns.keys())}"
            )

        pattern = patterns[cache_type]
        cleared_count = 0

        try:
            # Scan and delete matching keys
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                cleared_count = redis_client.delete(*keys)

            logger.info(f"✅ Cleared {cleared_count} cache keys with pattern '{pattern}'")

            return {
                "success": True,
                "cache_type": cache_type,
                "pattern": pattern,
                "keys_cleared": cleared_count,
                "cleared_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Failed to clear cache: {e}")
            return {
                "success": False,
                "cache_type": cache_type,
                "error": str(e),
                "note": "Cache clear failed - check Redis connection"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Cache clear endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
