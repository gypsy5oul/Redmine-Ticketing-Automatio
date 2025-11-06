#!/usr/bin/env python3
"""
SLA Service - Microservice for SLA policy management and tracking

Port: 8004
Dependencies: Shared PostgreSQL database, Redis

Endpoints:
- GET /api/v1/sla/policies - List SLA policies
- POST /api/v1/sla/policies - Create SLA policy
- PUT /api/v1/sla/policies/{id} - Update policy
- DELETE /api/v1/sla/policies/{id} - Delete policy
- GET /api/v1/sla/tracker/{ticket_id} - Get SLA status
- GET /api/v1/sla/at-risk - Get at-risk tickets
- POST /api/v1/sla/{ticket_id}/pause - Pause SLA
- POST /api/v1/sla/{ticket_id}/resume - Resume SLA
"""

import os
import sys
import enum
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# FastAPI
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Import shared auth and logging utilities
from shared.auth_utils import (
    setup_logging,
    log_request,
    get_current_user,
    require_admin,
    User
)

# Database
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime,
    ForeignKey, Float, Text, Enum, func, and_
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship

# Security
from jose import JWTError, jwt

# Redis
import redis

# Logging
from loguru import logger

# ============================================================================
# SETTINGS
# ============================================================================

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    SERVICE_NAME: str = "sla-service"
    SERVICE_PORT: int = 8004

    class Config:
        env_file = ".env"

settings = Settings()

# ============================================================================
# DATABASE
# ============================================================================

Base = declarative_base()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Redis
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    logger.info(f"✅ Connected to Redis")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}")
    redis_client = None

# ============================================================================
# MODELS
# ============================================================================

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    role = Column(Enum(UserRole, name='user_role'), default=UserRole.VIEWER)
    active = Column(Boolean, default=True)

class SLAStatus(str, enum.Enum):
    WITHIN_SLA = "within_sla"
    AT_RISK = "at_risk"
    CRITICAL = "critical"
    BREACHED = "breached"

class SLAPolicy(Base):
    __tablename__ = "sla_policies"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(String(50), unique=True, nullable=False, index=True)
    response_time_minutes = Column(Integer, nullable=False)
    resolution_time_minutes = Column(Integer, nullable=False)
    escalation_time_minutes = Column(Integer, nullable=False)
    business_hours_only = Column(Boolean, default=True)
    environment = Column(String(50))
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(String(200))

    sla_trackers = relationship("SLATracker", back_populates="policy")

class SLATracker(Base):
    __tablename__ = "sla_trackers"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), unique=True, index=True)
    policy_id = Column(Integer, ForeignKey("sla_policies.id"))
    status = Column(Enum(SLAStatus, name='sla_status'), default=SLAStatus.WITHIN_SLA, index=True)
    response_deadline = Column(DateTime(timezone=True), nullable=False)
    resolution_deadline = Column(DateTime(timezone=True), nullable=False)
    escalation_deadline = Column(DateTime(timezone=True), nullable=False)
    actual_response_time = Column(DateTime(timezone=True))
    actual_resolution_time = Column(DateTime(timezone=True))
    response_breached = Column(Boolean, default=False)
    resolution_breached = Column(Boolean, default=False)
    escalation_triggered = Column(Boolean, default=False)
    response_time_consumed = Column(Integer, default=0)
    resolution_time_consumed = Column(Integer, default=0)
    response_breach_minutes = Column(Integer)
    resolution_breach_minutes = Column(Integer)
    paused = Column(Boolean, default=False)
    paused_at = Column(DateTime(timezone=True))
    total_paused_minutes = Column(Integer, default=0)
    warning_alert_sent = Column(Boolean, default=False)
    critical_alert_sent = Column(Boolean, default=False)
    breach_alert_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    policy = relationship("SLAPolicy", back_populates="sla_trackers")
    breaches = relationship("SLABreach", back_populates="tracker")

class SLABreach(Base):
    __tablename__ = "sla_breaches"

    id = Column(Integer, primary_key=True, index=True)
    tracker_id = Column(Integer, ForeignKey("sla_trackers.id", ondelete="CASCADE"), index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)
    breach_type = Column(String(50), nullable=False)
    breach_minutes = Column(Integer, nullable=False)
    priority = Column(String(50), index=True)
    environment = Column(String(50))
    assigned_to_id = Column(Integer)
    team_level = Column(String(10))
    root_cause = Column(Text)
    remediation_action = Column(Text)
    breached_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True))

    tracker = relationship("SLATracker", back_populates="breaches")

class TicketHistory(Base):
    __tablename__ = "ticket_history"
    id = Column(Integer, primary_key=True, index=True)
    redmine_ticket_id = Column(Integer, unique=True, nullable=False)
    subject = Column(String(500))
    priority = Column(String(50))
    status = Column(String(50))
    sla_deadline = Column(DateTime(timezone=True))
    sla_breached = Column(Boolean, default=False)

# ============================================================================
# SECURITY
# ============================================================================
# Note: Authentication functions (get_current_user, require_admin, decode_token)
# are imported from shared/auth_utils.py at the top of this file.
# No local overrides needed - the shared implementations handle token extraction correctly.

# ============================================================================
# SLA MANAGER SERVICE
# ============================================================================

class SLAManager:
    """SLA management logic"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = redis_client
        self._default_policies = {
            "P1(Critical)": dict(response=15, resolution=240, escalation=120),
            "P2(High)": dict(response=60, resolution=480, escalation=240),
            "P3(Medium)": dict(response=120, resolution=720, escalation=360),
            "P4(Low)": dict(response=240, resolution=1440, escalation=720),
            "P5(Trivial)": dict(response=480, resolution=2880, escalation=1440),
        }

    def get_policy(self, priority: str, environment: str = None) -> Optional[SLAPolicy]:
        """Get SLA policy"""
        query = self.db.query(SLAPolicy).filter(
            SLAPolicy.priority == priority,
            SLAPolicy.active == True
        )

        if environment:
            policy = query.filter(SLAPolicy.environment == environment).first()
            if policy:
                return policy

        policy = query.filter(SLAPolicy.environment == None).first()
        if policy:
            return policy

        # Create default
        defaults = self._default_policies.get(priority)
        if not defaults:
            return None

        policy = SLAPolicy(
            priority=priority,
            response_time_minutes=defaults["response"],
            resolution_time_minutes=defaults["resolution"],
            escalation_time_minutes=defaults["escalation"],
            environment=None,
            business_hours_only=True,
            active=True,
            created_by="system_auto"
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        logger.info(f"✅ Created default SLA policy for {priority}")
        return policy

    def start_tracking(self, ticket_id: int, priority: str, environment: str = None) -> Optional[SLATracker]:
        """Start SLA tracking"""
        try:
            existing = self.db.query(SLATracker).filter(SLATracker.ticket_id == ticket_id).first()
            if existing:
                return existing

            policy = self.get_policy(priority, environment)
            if not policy:
                logger.error(f"No SLA policy for {priority}/{environment}")
                return None

            now = datetime.now(timezone.utc)
            tracker = SLATracker(
                ticket_id=ticket_id,
                policy_id=policy.id,
                status=SLAStatus.WITHIN_SLA,
                response_deadline=now + timedelta(minutes=policy.response_time_minutes),
                resolution_deadline=now + timedelta(minutes=policy.resolution_time_minutes),
                escalation_deadline=now + timedelta(minutes=policy.escalation_time_minutes)
            )

            self.db.add(tracker)
            self.db.commit()
            self.db.refresh(tracker)

            logger.info(f"✅ SLA tracking started for ticket {ticket_id}")
            return tracker

        except Exception as e:
            logger.error(f"❌ SLA tracking failed: {e}")
            self.db.rollback()
            return None

    def update_status(self, ticket_id: int) -> Optional[SLATracker]:
        """Update SLA status"""
        tracker = self.db.query(SLATracker).filter(SLATracker.ticket_id == ticket_id).first()
        if not tracker or tracker.paused:
            return tracker

        now = datetime.now(timezone.utc)

        # Check breaches
        if not tracker.actual_resolution_time and now > tracker.resolution_deadline:
            tracker.resolution_breached = True
            tracker.resolution_breach_minutes = int((now - tracker.resolution_deadline).total_seconds() / 60)
            tracker.status = SLAStatus.BREACHED

            if not tracker.breach_alert_sent:
                self._record_breach(tracker)
                tracker.breach_alert_sent = True
        else:
            # Calculate percentage
            total_minutes = tracker.policy.resolution_time_minutes
            elapsed = (now - tracker.created_at).total_seconds() / 60
            percentage = (elapsed / total_minutes) * 100 if total_minutes > 0 else 0

            if percentage >= 90:
                tracker.status = SLAStatus.CRITICAL
            elif percentage >= 80:
                tracker.status = SLAStatus.AT_RISK

        self.db.commit()
        return tracker

    def _record_breach(self, tracker: SLATracker):
        """Record SLA breach"""
        breach = SLABreach(
            tracker_id=tracker.id,
            ticket_id=tracker.ticket_id,
            breach_type="resolution",
            breach_minutes=tracker.resolution_breach_minutes or 0,
            priority=tracker.policy.priority
        )
        self.db.add(breach)
        logger.warning(f"⚠️ SLA BREACH recorded for ticket {tracker.ticket_id}")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="SLA Service", description="SLA policy management and tracking", version="1.0.0")

# Setup enhanced logging with request tracking
logger = setup_logging("sla-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/sla/policies", tags=["SLA"])
async def get_policies(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """List all SLA policies - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/sla/policies")
    try:
        policies = db.query(SLAPolicy).filter(SLAPolicy.active == True).all()
        return {
            "success": True,
            "count": len(policies),
            "policies": [
                {
                    "id": p.id,
                    "priority": p.priority,
                    "response_time_minutes": p.response_time_minutes,
                    "resolution_time_minutes": p.resolution_time_minutes,
                    "escalation_time_minutes": p.escalation_time_minutes,
                    "environment": p.environment,
                    "business_hours_only": p.business_hours_only
                }
                for p in policies
            ]
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/sla/policies", tags=["SLA"])
async def create_policy(
    user: User = Depends(require_admin),
    request: Request = None,
    policy_data: dict = None,
    db: Session = Depends(get_db)
):
    """Create SLA policy - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, "POST /api/v1/sla/policies")
    try:
        policy = SLAPolicy(
            priority=policy_data.get("priority"),
            response_time_minutes=policy_data.get("response_time_minutes"),
            resolution_time_minutes=policy_data.get("resolution_time_minutes"),
            escalation_time_minutes=policy_data.get("escalation_time_minutes"),
            environment=policy_data.get("environment"),
            business_hours_only=policy_data.get("business_hours_only", True),
            created_by=user.username
        )

        db.add(policy)
        db.commit()
        db.refresh(policy)

        logger.info(f"✅ Created SLA policy for {policy.priority}")
        return {"success": True, "policy_id": policy.id}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/sla/policies/{policy_id}", tags=["SLA"])
async def update_policy(
    policy_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    policy_data: dict = None,
    db: Session = Depends(get_db)
):
    """Update SLA policy - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"PUT /api/v1/sla/policies/{policy_id}")
    try:
        policy = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")

        if "response_time_minutes" in policy_data:
            policy.response_time_minutes = policy_data["response_time_minutes"]
        if "resolution_time_minutes" in policy_data:
            policy.resolution_time_minutes = policy_data["resolution_time_minutes"]
        if "escalation_time_minutes" in policy_data:
            policy.escalation_time_minutes = policy_data["escalation_time_minutes"]

        db.commit()
        logger.info(f"✅ Updated SLA policy {policy_id}")
        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sla/tracker/{ticket_id}", tags=["SLA"])
async def get_sla_status(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get SLA status for ticket - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"GET /api/v1/sla/tracker/{ticket_id}")
    try:
        tracker = db.query(SLATracker).filter(SLATracker.ticket_id == ticket_id).first()
        if not tracker:
            raise HTTPException(status_code=404, detail="SLA tracker not found")

        now = datetime.now(timezone.utc)
        time_remaining = int((tracker.resolution_deadline - now).total_seconds() / 60)

        return {
            "success": True,
            "sla": {
                "status": tracker.status.value,
                "response_deadline": tracker.response_deadline.isoformat(),
                "resolution_deadline": tracker.resolution_deadline.isoformat(),
                "time_remaining_minutes": time_remaining,
                "response_breached": tracker.response_breached,
                "resolution_breached": tracker.resolution_breached,
                "paused": tracker.paused
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get SLA status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sla/at-risk", tags=["SLA"])
async def get_at_risk_tickets(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get tickets at risk of SLA breach - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/sla/at-risk")
    try:
        trackers = db.query(SLATracker).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL])
        ).all()

        return {
            "success": True,
            "count": len(trackers),
            "tickets": [
                {
                    "ticket_id": t.ticket_id,
                    "status": t.status.value,
                    "resolution_deadline": t.resolution_deadline.isoformat(),
                    "time_remaining_minutes": int((t.resolution_deadline - datetime.now(timezone.utc)).total_seconds() / 60)
                }
                for t in trackers
            ]
        }

    except Exception as e:
        logger.error(f"❌ Failed to get at-risk tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/sla/{ticket_id}/pause", tags=["SLA"])
async def pause_sla(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Pause SLA tracking - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"POST /api/v1/sla/{ticket_id}/pause")
    try:
        tracker = db.query(SLATracker).filter(SLATracker.ticket_id == ticket_id).first()
        if not tracker:
            raise HTTPException(status_code=404, detail="SLA tracker not found")

        tracker.paused = True
        tracker.paused_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"⏸️ SLA paused for ticket {ticket_id}")
        return {"success": True, "message": "SLA paused"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to pause SLA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/sla/{ticket_id}/resume", tags=["SLA"])
async def resume_sla(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Resume SLA tracking - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"POST /api/v1/sla/{ticket_id}/resume")
    try:
        tracker = db.query(SLATracker).filter(SLATracker.ticket_id == ticket_id).first()
        if not tracker:
            raise HTTPException(status_code=404, detail="SLA tracker not found")

        if tracker.paused and tracker.paused_at:
            paused_duration = int((datetime.now(timezone.utc) - tracker.paused_at).total_seconds() / 60)
            tracker.total_paused_minutes += paused_duration

            # Extend deadlines
            tracker.response_deadline = tracker.response_deadline + timedelta(minutes=paused_duration)
            tracker.resolution_deadline = tracker.resolution_deadline + timedelta(minutes=paused_duration)
            tracker.escalation_deadline = tracker.escalation_deadline + timedelta(minutes=paused_duration)

        tracker.paused = False
        tracker.paused_at = None
        db.commit()

        logger.info(f"▶️ SLA resumed for ticket {ticket_id}")
        return {"success": True, "message": "SLA resumed"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to resume SLA: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Starting {settings.SERVICE_NAME} on port {settings.SERVICE_PORT}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
