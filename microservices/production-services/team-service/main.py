#!/usr/bin/env python3
"""
Team Service - Microservice for team member and skills management

Port: 8003
Dependencies: Shared PostgreSQL database

Endpoints:
- GET /api/v1/team/members - List all team members
- GET /api/v1/team/members/{id} - Get single team member
- POST /api/v1/team/members - Create team member
- PUT /api/v1/team/members/{id} - Update team member
- DELETE /api/v1/team/members/{id} - Deactivate team member
- GET /api/v1/team/members/{id}/performance - Get member performance
- GET /api/v1/team/skills - List all skills
- POST /api/v1/team/skills - Create skill
"""

import os
import sys
import enum
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# FastAPI
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Import shared auth and logging utilities
from shared.auth_utils import (
    setup_logging,
    log_request,
    log_error,
    get_current_user,
    require_admin,
    require_manager,
    User
)

# Database
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime,
    ForeignKey, Float, Text, Enum, Table, and_, func, case
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship

# Security
from passlib.context import CryptContext
from jose import JWTError, jwt

# Redis
import redis

# Logging
from loguru import logger

# ============================================================================
# SETTINGS & CONFIGURATION
# ============================================================================

class Settings(BaseSettings):
    """Service configuration"""
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets"
    )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY",
        "your-secret-key-change-in-production"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Service
    SERVICE_NAME: str = "team-service"
    SERVICE_PORT: int = 8003

    class Config:
        env_file = ".env"

settings = Settings()

# ============================================================================
# DATABASE SETUP
# ============================================================================

Base = declarative_base()

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Redis connection
try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5
    )
    redis_client.ping()
    logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}. Continuing without cache.")
    redis_client = None

def get_redis():
    """Redis dependency"""
    return redis_client

# ============================================================================
# MODELS
# ============================================================================

# --- User Role Enum (for JWT validation) ---
class UserRole(str, enum.Enum):
    """User roles"""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"

# --- User Model (for JWT validation) ---
class User(Base):
    """User model - minimal for JWT validation"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(200))
    role = Column(Enum(UserRole, name='user_role'), default=UserRole.VIEWER, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    team_member = relationship("TeamMember", back_populates="user", uselist=False)

# --- Team Enums ---
class TeamLevel(str, enum.Enum):
    """Team levels for escalation hierarchy"""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

class SkillLevel(str, enum.Enum):
    """Skill proficiency levels"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

# --- Ticket Enums (minimal for performance tracking) ---
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

class TicketCategory(str, enum.Enum):
    """Ticket categories"""
    KUBERNETES = "kubernetes"
    DATABASE = "database"
    NETWORK = "network"
    CICD = "cicd"
    MESSAGING = "messaging"
    STORAGE = "storage"
    APPLICATION = "application"
    SECURITY = "security"
    OTHER = "other"

class ComplexityLevel(str, enum.Enum):
    """Ticket complexity levels"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"

# --- Association Table ---
team_member_skills = Table(
    'team_member_skills',
    Base.metadata,
    Column('team_member_id', Integer, ForeignKey('team_members.id', ondelete='CASCADE')),
    Column('skill_id', Integer, ForeignKey('skills.id', ondelete='CASCADE')),
    Column('proficiency_level', Enum(SkillLevel, name='skill_level'), default=SkillLevel.INTERMEDIATE),
    Column('years_experience', Float, default=0.0),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

# --- Skill Model ---
class Skill(Base):
    """Skills/Technologies that team members can have"""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False)
    description = Column(String(500))
    keywords = Column(String(1000))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team_members = relationship(
        "TeamMember",
        secondary=team_member_skills,
        back_populates="skills"
    )

# --- TeamMember Model ---
class TeamMember(Base):
    """Team members with skills and capacity configuration"""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)
    redmine_user_id = Column(Integer, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    team_level = Column(Enum(TeamLevel, name='team_level'), nullable=False, index=True)
    max_tickets = Column(Integer, default=8)
    active = Column(Boolean, default=True, index=True)

    # Timezone
    timezone = Column(String(50), default="Asia/Kolkata")
    work_start_hour = Column(Integer, default=9)
    work_end_hour = Column(Integer, default=18)

    # Performance tracking
    total_tickets_assigned = Column(Integer, default=0)
    total_tickets_resolved = Column(Integer, default=0)
    avg_resolution_time_hours = Column(Float, default=0.0)
    sla_compliance_rate = Column(Float, default=100.0)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_assigned_at = Column(DateTime(timezone=True))

    # Relationships
    skills = relationship(
        "Skill",
        secondary=team_member_skills,
        back_populates="team_members"
    )
    user = relationship("User", back_populates="team_member", uselist=False)
    performance_metrics = relationship("PerformanceMetric", back_populates="team_member")

# --- Ticket Model (minimal - for performance queries) ---
class TicketHistory(Base):
    """Minimal ticket model for performance tracking"""
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    redmine_ticket_id = Column(Integer, unique=True, nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    description = Column(Text)

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    team_level = Column(String(10), nullable=False, index=True)

    # Classification
    priority = Column(Enum(TicketPriority, name='ticket_priority'), nullable=False, index=True)
    status = Column(Enum(TicketStatus, name='ticket_status'), default=TicketStatus.NEW, index=True)
    category = Column(Enum(TicketCategory, name='ticket_category'), index=True)

    # SLA
    sla_breached = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# --- Collaboration Model ---
class TicketCollaboration(Base):
    """Track multiple engineers collaborating on tickets"""
    __tablename__ = "ticket_collaborations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"))
    role = Column(String(50))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

# --- Performance Metrics Model ---
class PerformanceMetric(Base):
    """Daily performance metrics per team member"""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    team_member_id = Column(
        Integer,
        ForeignKey("team_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    date = Column(DateTime, nullable=False, index=True)

    # Ticket counts
    tickets_assigned = Column(Integer, default=0)
    tickets_resolved = Column(Integer, default=0)
    tickets_escalated = Column(Integer, default=0)
    tickets_reopened = Column(Integer, default=0)

    # Time metrics
    avg_resolution_time_hours = Column(Float)

    # SLA metrics
    sla_met_count = Column(Integer, default=0)
    sla_breached_count = Column(Integer, default=0)
    sla_compliance_rate = Column(Float)

    # Collaboration
    collaborative_tickets_count = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    team_member = relationship("TeamMember", back_populates="performance_metrics")

# ============================================================================
# SECURITY & AUTHENTICATION
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Token payload

    Raises:
        JWTError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    token: str = Depends(lambda: None),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from JWT token

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    username: str = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    user = db.query(User).filter(User.username == username).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )

    return user

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require ADMIN or SUPER_ADMIN role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this resource"
        )
    return current_user

# ============================================================================
# WORKLOAD MANAGER SERVICE
# ============================================================================

class WorkloadManager:
    """Manages team workload and capacity"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()

    def get_current_workload(self, user_id: int, use_cache: bool = True) -> int:
        """Get current workload for a user (active tickets only)"""
        try:
            # Try cache first
            if use_cache and self.redis:
                cached = self.redis.get(f"workload:user:{user_id}")
                if cached:
                    return int(cached)

            # Query database
            workload = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == user_id,
                TicketHistory.status.in_([
                    TicketStatus.ASSIGNED,
                    TicketStatus.IN_PROGRESS
                ])
            ).count()

            # Cache result
            if self.redis:
                self.redis.setex(f"workload:user:{user_id}", 300, workload)

            return workload

        except Exception as e:
            logger.error(f"❌ Error getting workload for user {user_id}: {e}")
            return 0

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Team Service",
    description="Team member and skills management microservice",
    version="1.0.0"
)

# Setup enhanced logging with request tracking
logger = setup_logging("team-service", os.getenv("LOG_LEVEL", "INFO"))

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ============================================================================
# TEAM ENDPOINTS
# ============================================================================

@app.get("/api/v1/team/members", tags=["Team"])
async def get_team_members(
    user: User = Depends(get_current_user),
    request: Request = None,
    team_level: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get all team members - Requires: Any authenticated user

    Args:
        team_level: Filter by team level (L1, L2, L3)
        active_only: Only return active members (default: True)
    """
    log_request(logger, request, user.id, "GET /api/v1/team/members")
    try:
        query = db.query(TeamMember)

        if active_only:
            query = query.filter(TeamMember.active == True)

        if team_level:
            query = query.filter(TeamMember.team_level == TeamLevel(team_level))

        members = query.all()
        workload_manager = WorkloadManager(db)

        return {
            "success": True,
            "count": len(members),
            "members": [
                {
                    "id": m.id,
                    "redmine_user_id": m.redmine_user_id,
                    "user_id": m.user_id,
                    "name": m.name,
                    "email": m.email,
                    "team_level": m.team_level.value,
                    "max_tickets": m.max_tickets,
                    "current_tickets": workload_manager.get_current_workload(m.id),
                    "active": m.active,
                    "timezone": m.timezone,
                    "work_hours": f"{m.work_start_hour}:00 - {m.work_end_hour}:00",
                    "work_start_hour": m.work_start_hour,
                    "work_end_hour": m.work_end_hour,
                    "total_tickets_assigned": m.total_tickets_assigned,
                    "total_tickets_resolved": m.total_tickets_resolved,
                    "sla_compliance_rate": m.sla_compliance_rate,
                    "skills": [{"id": s.id, "name": s.name, "category": s.category} for s in m.skills]
                }
                for m in members
            ]
        }
    except Exception as e:
        logger.error(f"❌ Failed to fetch team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/team/members/{member_id}", tags=["Team"])
async def get_team_member(
    member_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get a single team member by ID - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"GET /api/v1/team/members/{member_id}")
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        return {
            "success": True,
            "member": {
                "id": member.id,
                "redmine_user_id": member.redmine_user_id,
                "user_id": member.user_id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets,
                "active": member.active,
                "timezone": member.timezone,
                "work_start_hour": member.work_start_hour,
                "work_end_hour": member.work_end_hour,
                "total_tickets_assigned": member.total_tickets_assigned,
                "total_tickets_resolved": member.total_tickets_resolved,
                "sla_compliance_rate": member.sla_compliance_rate,
                "skills": [{"id": s.id, "name": s.name, "category": s.category} for s in member.skills]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/team/members", tags=["Team"])
async def create_team_member(
    user: User = Depends(require_admin),
    request: Request = None,
    data: dict = None,
    db: Session = Depends(get_db)
):
    """
    Create a new team member - Requires: Admin or Super Admin role

    Note: In production, this would fetch from Redmine.
    For now, accepts all data in request body.
    """
    log_request(logger, request, user.id, "POST /api/v1/team/members")
    try:
        redmine_user_id = data.get("redmine_user_id")
        team_level_str = data.get("team_level")
        name = data.get("name")
        email = data.get("email")
        max_tickets = data.get("max_tickets", 8)
        timezone = data.get("timezone", "Asia/Kolkata")
        work_start_hour = data.get("work_start_hour", 9)
        work_end_hour = data.get("work_end_hour", 18)
        skill_ids = data.get("skills", [])

        if not redmine_user_id:
            raise HTTPException(status_code=400, detail="redmine_user_id is required")
        if not team_level_str:
            raise HTTPException(status_code=400, detail="team_level is required")
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        if not email:
            raise HTTPException(status_code=400, detail="email is required")

        # Check if member already exists
        existing = db.query(TeamMember).filter(
            TeamMember.redmine_user_id == redmine_user_id
        ).first()

        if not existing:
            existing = db.query(TeamMember).filter(
                TeamMember.email == email
            ).first()

        if existing:
            if existing.active:
                raise HTTPException(
                    status_code=400,
                    detail=f"Team member with Redmine ID {redmine_user_id} already exists"
                )

            # Reactivate
            existing.name = name
            existing.email = email
            existing.team_level = TeamLevel(team_level_str)
            existing.max_tickets = max_tickets
            existing.timezone = timezone
            existing.work_start_hour = work_start_hour
            existing.work_end_hour = work_end_hour
            existing.active = True

            # Update skills
            if skill_ids:
                existing.skills = []
                skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
                existing.skills = skills

            db.commit()
            db.refresh(existing)

            logger.info(f"✅ Reactivated team member: {existing.name} ({team_level_str})")

            return {
                "success": True,
                "message": f"Team member {existing.name} reactivated successfully",
                "member": {
                    "id": existing.id,
                    "redmine_user_id": existing.redmine_user_id,
                    "name": existing.name,
                    "email": existing.email,
                    "team_level": existing.team_level.value,
                    "max_tickets": existing.max_tickets
                }
            }

        # Create new member
        member = TeamMember(
            redmine_user_id=redmine_user_id,
            name=name,
            email=email,
            team_level=TeamLevel(team_level_str),
            max_tickets=max_tickets,
            timezone=timezone,
            work_start_hour=work_start_hour,
            work_end_hour=work_end_hour,
            active=True
        )

        db.add(member)
        db.flush()

        # Associate skills
        if skill_ids:
            skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            member.skills = skills

        db.commit()
        db.refresh(member)

        logger.info(f"✅ Created team member: {member.name} ({team_level_str})")

        return {
            "success": True,
            "message": f"Team member {member.name} created successfully",
            "member": {
                "id": member.id,
                "redmine_user_id": member.redmine_user_id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/team/members/{member_id}", tags=["Team"])
async def update_team_member(
    member_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    member_data: dict = None,
    db: Session = Depends(get_db)
):
    """Update team member details - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"PUT /api/v1/team/members/{member_id}")
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        logger.info(f"📝 Updating team member {member_id} ({member.name})")

        # Update fields
        if 'team_level' in member_data:
            member.team_level = TeamLevel(member_data['team_level'])
        if 'max_tickets' in member_data:
            member.max_tickets = member_data['max_tickets']
        if 'active' in member_data:
            member.active = member_data['active']
        if 'timezone' in member_data:
            member.timezone = member_data['timezone']
        if 'work_start_hour' in member_data:
            member.work_start_hour = member_data['work_start_hour']
        if 'work_end_hour' in member_data:
            member.work_end_hour = member_data['work_end_hour']

        # Update skills
        if 'skills' in member_data:
            skill_ids = member_data['skills']
            member.skills = []
            if skill_ids:
                skills = db.query(Skill).filter(Skill.id.in_(skill_ids)).all()
                member.skills = skills

        db.commit()
        db.refresh(member)

        logger.info(f"✅ Updated team member: {member.name}")

        return {
            "success": True,
            "message": f"Team member {member.name} updated successfully",
            "member": {
                "id": member.id,
                "name": member.name,
                "team_level": member.team_level.value,
                "max_tickets": member.max_tickets,
                "active": member.active
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/team/members/{member_id}", tags=["Team"])
async def delete_team_member(
    member_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Soft delete a team member (mark as inactive) - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"DELETE /api/v1/team/members/{member_id}")
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        # Soft delete
        member.active = False
        db.commit()

        logger.info(f"✅ Deactivated team member: {member.name}")

        return {
            "success": True,
            "message": f"Team member {member.name} deactivated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/team/members/{member_id}/performance", tags=["Team"])
async def get_member_performance(
    member_id: int,
    user: User = Depends(require_manager),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Get individual team member performance metrics - Requires: Manager, Admin, or Super Admin role
    """
    log_request(logger, request, user.id, f"GET /api/v1/team/members/{member_id}/performance")
    try:
        # Get team member
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Team member not found")

        # Get all tickets
        tickets = db.query(TicketHistory).filter(
            TicketHistory.assigned_to_id == member_id
        ).all()

        # Calculate metrics
        total_tickets = len(tickets)
        tickets_open = sum(1 for t in tickets if t.status in [TicketStatus.NEW, TicketStatus.ASSIGNED])
        tickets_in_progress = sum(1 for t in tickets if t.status == TicketStatus.IN_PROGRESS)
        tickets_resolved = sum(1 for t in tickets if t.status == TicketStatus.RESOLVED)
        tickets_closed = sum(1 for t in tickets if t.status == TicketStatus.CLOSED)
        tickets_on_hold = sum(1 for t in tickets if t.status == TicketStatus.PENDING)

        # SLA compliance
        tickets_breached = sum(1 for t in tickets if t.sla_breached)
        sla_compliance_rate = ((total_tickets - tickets_breached) / total_tickets * 100) if total_tickets > 0 else 100.0

        # Average resolution time
        resolution_times = []
        for ticket in tickets:
            if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                if ticket.closed_at and ticket.created_at:
                    resolution_time = (ticket.closed_at - ticket.created_at).total_seconds() / 3600
                    resolution_times.append(resolution_time)

        avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else 0.0

        # Current workload
        current_tickets = tickets_open + tickets_in_progress + tickets_on_hold
        max_tickets = member.max_tickets or 10
        capacity_percentage = (current_tickets / max_tickets * 100) if max_tickets > 0 else 0.0

        # Recent tickets
        recent_tickets = sorted(tickets, key=lambda t: t.updated_at or t.created_at, reverse=True)[:10]
        recent_tickets_data = [
            {
                "id": ticket.id,
                "redmine_ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "sla_breached": ticket.sla_breached,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None
            }
            for ticket in recent_tickets
        ]

        # Workload trend (last 30 days)
        workload_trend = []
        now = datetime.utcnow()
        for i in range(30, 0, -1):
            date_obj = now - timedelta(days=i)
            date_start = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            date_end = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)

            active_count = 0
            for ticket in tickets:
                ticket_created = ticket.created_at.replace(tzinfo=None) if ticket.created_at else None
                ticket_closed = ticket.closed_at.replace(tzinfo=None) if ticket.closed_at else None

                if ticket_created and ticket_created <= date_end:
                    if not ticket_closed or ticket_closed >= date_start:
                        active_count += 1

            workload_trend.append({
                "date": date_obj.strftime("%Y-%m-%d"),
                "active_tickets": active_count
            })

        # Collaboration stats
        collaborations = db.query(TicketCollaboration).filter(
            TicketCollaboration.team_member_id == member_id,
            TicketCollaboration.is_active == True
        ).count()

        return {
            "success": True,
            "member": {
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level.value,
                "active": member.active,
                "current_tickets": current_tickets,
                "max_tickets": max_tickets,
                "capacity_percentage": round(capacity_percentage, 2)
            },
            "performance": {
                "total_tickets_assigned": total_tickets,
                "tickets_open": tickets_open,
                "tickets_in_progress": tickets_in_progress,
                "tickets_resolved": tickets_resolved,
                "tickets_closed": tickets_closed,
                "tickets_on_hold": tickets_on_hold,
                "tickets_breached": tickets_breached,
                "sla_compliance_rate": round(sla_compliance_rate, 2),
                "avg_resolution_time_hours": round(avg_resolution_time, 2),
                "active_collaborations": collaborations
            },
            "recent_tickets": recent_tickets_data,
            "workload_trend": workload_trend
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get member performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SKILLS ENDPOINTS
# ============================================================================

@app.get("/api/v1/team/skills", tags=["Skills"])
async def get_skills(
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get all available skills - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/team/skills")
    try:
        skills = db.query(Skill).all()

        return {
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "category": s.category,
                    "description": s.description
                }
                for s in skills
            ],
            "total": len(skills)
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/team/skills", tags=["Skills"])
async def create_skill(
    user: User = Depends(require_admin),
    request: Request = None,
    name: str = None,
    category: str = None,
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new skill - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, "POST /api/v1/team/skills")
    try:
        # Check if skill already exists
        existing = db.query(Skill).filter(Skill.name == name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Skill already exists")

        skill = Skill(
            name=name,
            category=category,
            description=description
        )

        db.add(skill)
        db.commit()
        db.refresh(skill)

        return {
            "success": True,
            "skill": {
                "id": skill.id,
                "name": skill.name,
                "category": skill.category,
                "description": skill.description
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to create skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info(f"🚀 Starting {settings.SERVICE_NAME} on port {settings.SERVICE_PORT}")
    logger.info(f"📊 Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.SERVICE_PORT,
        reload=True
    )
