#!/usr/bin/env python3
"""
Workload Service - Real-time capacity tracking and load balancing

Port: 8005
Dependencies: Shared PostgreSQL database, Redis

Endpoints:
- GET /api/v1/workload/team - Get team workload overview
- GET /api/v1/workload/member/{id} - Get member workload
- GET /api/v1/workload/capacity - Get capacity summary
"""

import os
import sys
import enum
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Enum, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from jose import jwt, JWTError
import redis

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Import shared auth and logging utilities
from shared.auth_utils import (
    setup_logging,
    log_request,
    get_current_user,
    User
)

# ============================================================================
# SETTINGS
# ============================================================================

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"
    SERVICE_NAME: str = "workload-service"
    SERVICE_PORT: int = 8005

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

# Redis
try:
    redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
    redis_client.ping()
except Exception as e:
    logger.warning(f"Redis unavailable: {e}")
    redis_client = None

# ============================================================================
# MODELS
# ============================================================================

class TeamLevel(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

class TicketStatus(str, enum.Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    redmine_user_id = Column(Integer, unique=True)
    name = Column(String(200))
    email = Column(String(200))
    team_level = Column(Enum(TeamLevel, name='team_level'))
    max_tickets = Column(Integer, default=8)
    active = Column(Boolean, default=True)

class TicketHistory(Base):
    __tablename__ = "ticket_history"
    id = Column(Integer, primary_key=True)
    redmine_ticket_id = Column(Integer)
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"))
    status = Column(String(50))

# ============================================================================
# WORKLOAD MANAGER
# ============================================================================

class WorkloadManager:
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis_client

    def get_current_workload(self, user_id: int) -> int:
        """Get current active tickets"""
        try:
            if self.redis:
                cached = self.redis.get(f"workload:user:{user_id}")
                if cached:
                    return int(cached)

            workload = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == user_id,
                TicketHistory.status.in_(["assigned", "in_progress"])
            ).count()

            if self.redis:
                self.redis.setex(f"workload:user:{user_id}", 300, workload)

            return workload
        except Exception as e:
            logger.error(f"Error getting workload: {e}")
            return 0

    def get_team_workload(self, team_level: str = None) -> List[dict]:
        """Get workload for team"""
        query = self.db.query(TeamMember).filter(TeamMember.active == True)

        if team_level:
            query = query.filter(TeamMember.team_level == TeamLevel(team_level))

        members = query.all()
        workload_data = []

        for member in members:
            current = self.get_current_workload(member.id)
            max_tickets = member.max_tickets
            utilization = (current / max_tickets * 100) if max_tickets > 0 else 0

            if current >= max_tickets:
                status = "at_capacity"
            elif current >= max_tickets * 0.8:
                status = "high_load"
            elif current >= max_tickets * 0.5:
                status = "moderate_load"
            else:
                status = "available"

            workload_data.append({
                "user_id": member.id,
                "name": member.name,
                "team_level": member.team_level.value,
                "current_tickets": current,
                "max_tickets": max_tickets,
                "utilization": round(utilization, 1),
                "status": status
            })

        return sorted(workload_data, key=lambda x: x['utilization'])

    def get_capacity_summary(self) -> dict:
        """Get overall capacity summary"""
        l1 = self.get_team_workload("L1")
        l2 = self.get_team_workload("L2")
        l3 = self.get_team_workload("L3")

        def calc_stats(data):
            if not data:
                return {"members": 0, "total_capacity": 0, "used_capacity": 0, "utilization": 0}
            return {
                "members": len(data),
                "total_capacity": sum(w['max_tickets'] for w in data),
                "used_capacity": sum(w['current_tickets'] for w in data),
                "utilization": round(sum(w['utilization'] for w in data) / len(data), 1) if data else 0
            }

        return {
            "l1": calc_stats(l1),
            "l2": calc_stats(l2),
            "l3": calc_stats(l3)
        }

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Workload Service", version="1.0.0")

# Setup enhanced logging with request tracking
logger = setup_logging("workload-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

@app.get("/api/v1/workload", tags=["Workload"])
async def get_workload(
    user: User = Depends(get_current_user),
    request: Request = None,
    level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get workload overview (alias for /team endpoint) - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/workload")
    try:
        manager = WorkloadManager(db)
        workload = manager.get_team_workload(level)
        return {"success": True, "count": len(workload), "workload": workload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/workload/team", tags=["Workload"])
async def get_team_workload(
    user: User = Depends(get_current_user),
    request: Request = None,
    team_level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get team workload - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/workload/team")
    try:
        manager = WorkloadManager(db)
        workload = manager.get_team_workload(team_level)
        return {"success": True, "count": len(workload), "workload": workload}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/workload/member/{member_id}", tags=["Workload"])
async def get_member_workload(
    member_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get member workload - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"GET /api/v1/workload/member/{member_id}")
    try:
        manager = WorkloadManager(db)
        current = manager.get_current_workload(member_id)

        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        return {
            "success": True,
            "member_id": member_id,
            "current_tickets": current,
            "max_tickets": member.max_tickets,
            "utilization": round((current / member.max_tickets * 100), 1) if member.max_tickets > 0 else 0
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/workload/capacity", tags=["Workload"])
async def get_capacity_summary(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get capacity summary - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/workload/capacity")
    try:
        manager = WorkloadManager(db)
        summary = manager.get_capacity_summary()
        return {"success": True, "capacity": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
