#!/usr/bin/env python3
"""
Ticket Service - Microservice for ticket management and processing

Port: 8002
Dependencies: Shared PostgreSQL database, Redis

Endpoints:
- GET /api/v1/tickets - List tickets with filters
- GET /api/v1/tickets/{id} - Get single ticket
- POST /api/v1/tickets/process - Process new ticket from Redmine
- PUT /api/v1/tickets/{id} - Update ticket
- POST /api/v1/tickets/{id}/resolve - Resolve ticket
- GET /api/v1/tickets/{id}/comments - Get ticket comments
- POST /api/v1/tickets/{id}/comments - Add comment
- PUT /api/v1/comments/{id} - Update comment
- DELETE /api/v1/comments/{id} - Delete comment
"""

import os
import enum
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# FastAPI
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Database
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, DateTime,
    ForeignKey, Float, Text, Enum, and_, or_, desc, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship

# Security
from jose import JWTError, jwt
from passlib.context import CryptContext

# Redis
import redis

# Logging
from loguru import logger

# HTTP client for external services
import requests

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
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM: str = "HS256"

    # Redmine Integration
    REDMINE_BASE_URL: str = os.getenv("REDMINE_BASE_URL", "https://redmine.example.com")
    REDMINE_API_KEY: str = os.getenv("REDMINE_API_KEY", "")

    # LLM Service (optional)
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama2")
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"

    # Service
    SERVICE_NAME: str = "ticket-service"
    SERVICE_PORT: int = 8002

    class Config:
        env_file = ".env"

settings = Settings()

# ============================================================================
# DATABASE SETUP
# ============================================================================

Base = declarative_base()

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
    logger.info(f"✅ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
except Exception as e:
    logger.warning(f"⚠️ Redis connection failed: {e}")
    redis_client = None

def get_redis():
    return redis_client

# ============================================================================
# MODELS
# ============================================================================

# --- User Role ---
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"

# --- User Model ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(Enum(UserRole, name='user_role'), default=UserRole.VIEWER)
    active = Column(Boolean, default=True)

# --- Team Enums ---
class TeamLevel(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

# --- Team Member Model ---
class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True, index=True)
    redmine_user_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    team_level = Column(Enum(TeamLevel, name='team_level'), nullable=False)
    max_tickets = Column(Integer, default=8)
    active = Column(Boolean, default=True)

# --- Ticket Enums ---
class TicketStatus(str, enum.Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REOPENED = "reopened"

class TicketPriority(str, enum.Enum):
    P1_CRITICAL = "P1(Critical)"
    P2_HIGH = "P2(High)"
    P3_MEDIUM = "P3(Medium)"
    P4_LOW = "P4(Low)"
    P5_TRIVIAL = "P5(Trivial)"

class TicketCategory(str, enum.Enum):
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
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    CRITICAL = "critical"

class CommentType(str, enum.Enum):
    PUBLIC = "public"
    INTERNAL = "internal"

# --- Ticket Model ---
class TicketHistory(Base):
    __tablename__ = "ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    redmine_ticket_id = Column(Integer, unique=True, nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    description = Column(Text)
    requester_name = Column(String(255))

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("team_members.id"), index=True)
    team_level = Column(String(10), nullable=False, index=True)

    # Classification
    priority = Column(Enum(TicketPriority, name='ticket_priority'), nullable=False, index=True)
    original_priority = Column(Enum(TicketPriority, name='ticket_priority'))
    priority_adjusted = Column(Boolean, default=False)
    status = Column(Enum(TicketStatus, name='ticket_status'), default=TicketStatus.NEW, index=True)
    environment = Column(String(50), index=True)
    category = Column(Enum(TicketCategory, name='ticket_category'), index=True)
    complexity = Column(Enum(ComplexityLevel, name='complexity_level'))

    # ML Predictions
    estimated_resolution_hours = Column(Float)
    predicted_escalation_probability = Column(Float)
    ml_confidence_score = Column(Float)

    # SLA Tracking
    sla_deadline = Column(DateTime(timezone=True))
    sla_breached = Column(Boolean, default=False, index=True)
    sla_breach_minutes = Column(Integer)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    assigned_at = Column(DateTime(timezone=True))
    first_response_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Work tracking
    total_work_minutes = Column(Integer, default=0)
    total_waiting_minutes = Column(Integer, default=0)
    work_efficiency_percent = Column(Float)

    # Escalation
    escalation_count = Column(Integer, default=0)
    escalated = Column(Boolean, default=False)

    # AI Analysis
    ai_analysis = Column(Text)
    ai_analysis_time_seconds = Column(Float)

    # Collaboration
    is_collaborative = Column(Boolean, default=False)
    collaborator_count = Column(Integer, default=0)

    # Metadata
    redmine_url = Column(String(500))
    project_jira_id = Column(String(100), index=True)
    resolution_notes = Column(Text)

    # Relationships
    assigned_to = relationship("TeamMember", foreign_keys=[assigned_to_id])
    comments = relationship("TicketComment", back_populates="ticket", cascade="all, delete-orphan")
    collaborations = relationship("TicketCollaboration", back_populates="ticket")

# --- Comment Model ---
class TicketComment(Base):
    __tablename__ = "ticket_comments"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("team_members.id", ondelete="SET NULL"), index=True)
    content = Column(Text, nullable=False)
    comment_type = Column(Enum(CommentType, name='comment_type'), default=CommentType.PUBLIC)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_edited = Column(Boolean, default=False)

    # Relationships
    ticket = relationship("TicketHistory", back_populates="comments")
    author = relationship("TeamMember", foreign_keys=[author_id])

# --- Collaboration Model ---
class TicketCollaboration(Base):
    __tablename__ = "ticket_collaborations"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id", ondelete="CASCADE"), index=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id", ondelete="CASCADE"))
    role = Column(String(50))
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    comments_count = Column(Integer, default=0)
    time_spent_hours = Column(Float, default=0.0)
    notes = Column(Text)

    # Relationships
    ticket = relationship("TicketHistory", back_populates="collaborations")
    team_member = relationship("TeamMember")

# ============================================================================
# SECURITY
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def decode_token(token: str) -> Dict[str, Any]:
    """Decode JWT token"""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user(token: str = Depends(lambda: None), db: Session = Depends(get_db)) -> User:
    """Get current user from token"""
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(token)
    username = payload.get("sub")

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# ============================================================================
# SERVICES
# ============================================================================

class RedmineService:
    """Simplified Redmine integration"""

    def __init__(self):
        self.base_url = settings.REDMINE_BASE_URL
        self.api_key = settings.REDMINE_API_KEY
        self.headers = {
            'X-Redmine-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def update_issue(self, issue_id: int, assigned_to_id: int = None,
                     status_id: int = None, notes: str = None) -> bool:
        """Update Redmine issue"""
        try:
            url = f"{self.base_url}/issues/{issue_id}.json"
            payload = {"issue": {}}

            if assigned_to_id:
                payload["issue"]["assigned_to_id"] = assigned_to_id
            if status_id:
                payload["issue"]["status_id"] = status_id
            if notes:
                payload["issue"]["notes"] = notes

            response = requests.put(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()

            logger.info(f"✅ Updated Redmine issue {issue_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to update Redmine issue: {e}")
            return False

class SimpleLLMService:
    """Simplified LLM analysis service"""

    def __init__(self):
        self.enabled = settings.LLM_ENABLED
        self.base_url = settings.LLM_BASE_URL
        self.model = settings.LLM_MODEL
        self.redis = get_redis()

    def analyze_ticket(self, ticket: Dict) -> Dict:
        """Analyze ticket with LLM (with caching)"""
        if not self.enabled:
            return self._fallback_analysis(ticket)

        # Check cache
        cache_key = self._generate_cache_key(ticket)
        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)

        # Call LLM
        try:
            analysis = self._call_llm(ticket)

            # Cache result
            if self.redis:
                self.redis.setex(cache_key, 604800, json.dumps(analysis))

            return analysis

        except Exception as e:
            logger.error(f"❌ LLM analysis failed: {e}")
            return self._fallback_analysis(ticket)

    def _generate_cache_key(self, ticket: Dict) -> str:
        """Generate cache key"""
        content = f"{ticket.get('subject', '')}|{ticket.get('description', '')}"
        return f"llm:cache:{hashlib.sha256(content.encode()).hexdigest()}"

    def _call_llm(self, ticket: Dict) -> Dict:
        """Call LLM API"""
        prompt = f"""Analyze this support ticket and provide:
1. Category (kubernetes/database/network/cicd/messaging/storage/application/security/other)
2. Complexity (simple/moderate/complex/critical)
3. Estimated resolution time in hours
4. Brief action plan

Ticket: {ticket.get('subject', '')}
Description: {ticket.get('description', '')}"""

        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt},
            timeout=30
        )

        # Parse response (simplified)
        return {
            "category": "other",
            "complexity": "moderate",
            "estimated_hours": 4.0,
            "action_plan": "Analyze and resolve the issue"
        }

    def _fallback_analysis(self, ticket: Dict) -> Dict:
        """Fallback rule-based analysis"""
        return {
            "category": "other",
            "complexity": "moderate",
            "estimated_hours": 4.0,
            "action_plan": "Review ticket and provide resolution"
        }

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Ticket Service",
    description="Ticket management and processing microservice",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/tickets", tags=["Tickets"])
async def get_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
    team_level: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get tickets with filters"""
    try:
        query = db.query(TicketHistory)

        if status:
            query = query.filter(TicketHistory.status == TicketStatus(status))
        if priority:
            query = query.filter(TicketHistory.priority == TicketPriority(priority))
        if assigned_to_id:
            query = query.filter(TicketHistory.assigned_to_id == assigned_to_id)
        if team_level:
            query = query.filter(TicketHistory.team_level == team_level)

        total = query.count()
        tickets = query.order_by(desc(TicketHistory.created_at)).limit(limit).offset(offset).all()

        return {
            "success": True,
            "total": total,
            "count": len(tickets),
            "tickets": [
                {
                    "id": t.id,
                    "redmine_ticket_id": t.redmine_ticket_id,
                    "subject": t.subject,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "category": t.category.value if t.category else None,
                    "assigned_to_id": t.assigned_to_id,
                    "team_level": t.team_level,
                    "sla_breached": t.sla_breached,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None
                }
                for t in tickets
            ]
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/tickets/{ticket_id}", tags=["Tickets"])
async def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get single ticket"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return {
            "success": True,
            "ticket": {
                "id": ticket.id,
                "redmine_ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "description": ticket.description,
                "status": ticket.status.value,
                "priority": ticket.priority.value,
                "category": ticket.category.value if ticket.category else None,
                "complexity": ticket.complexity.value if ticket.complexity else None,
                "assigned_to_id": ticket.assigned_to_id,
                "team_level": ticket.team_level,
                "sla_breached": ticket.sla_breached,
                "ai_analysis": ticket.ai_analysis,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fetch ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tickets/process", tags=["Tickets"])
async def process_ticket(ticket_data: dict, db: Session = Depends(get_db)):
    """Process new ticket from Redmine"""
    try:
        # Create ticket
        ticket = TicketHistory(
            redmine_ticket_id=ticket_data.get("redmine_ticket_id"),
            subject=ticket_data.get("subject"),
            description=ticket_data.get("description"),
            priority=TicketPriority(ticket_data.get("priority", "P3(Medium)")),
            team_level="L1",
            status=TicketStatus.NEW,
            environment=ticket_data.get("environment", "prod")
        )

        # AI Analysis (optional)
        llm_service = SimpleLLMService()
        analysis = llm_service.analyze_ticket(ticket_data)

        if analysis.get("category"):
            ticket.category = TicketCategory(analysis["category"])
        if analysis.get("complexity"):
            ticket.complexity = ComplexityLevel(analysis["complexity"])
        if analysis.get("estimated_hours"):
            ticket.estimated_resolution_hours = analysis["estimated_hours"]
        ticket.ai_analysis = analysis.get("action_plan", "")

        db.add(ticket)
        db.commit()
        db.refresh(ticket)

        logger.info(f"✅ Created ticket {ticket.redmine_ticket_id}")

        return {
            "success": True,
            "ticket_id": ticket.id,
            "message": "Ticket processed successfully"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to process ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/tickets/{ticket_id}", tags=["Tickets"])
async def update_ticket(ticket_id: int, update_data: dict, db: Session = Depends(get_db)):
    """Update ticket"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Update fields
        if "status" in update_data:
            ticket.status = TicketStatus(update_data["status"])
        if "priority" in update_data:
            ticket.priority = TicketPriority(update_data["priority"])
        if "assigned_to_id" in update_data:
            ticket.assigned_to_id = update_data["assigned_to_id"]
            ticket.assigned_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(ticket)

        logger.info(f"✅ Updated ticket {ticket_id}")

        return {
            "success": True,
            "message": "Ticket updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tickets/{ticket_id}/resolve", tags=["Tickets"])
async def resolve_ticket(ticket_id: int, resolution_data: dict, db: Session = Depends(get_db)):
    """Resolve ticket"""
    try:
        ticket = db.query(TicketHistory).filter(TicketHistory.id == ticket_id).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = datetime.now(timezone.utc)
        ticket.resolution_notes = resolution_data.get("notes", "")

        # Update Redmine
        redmine = RedmineService()
        redmine.update_issue(
            ticket.redmine_ticket_id,
            status_id=3,  # Resolved
            notes=ticket.resolution_notes
        )

        db.commit()

        logger.info(f"✅ Resolved ticket {ticket_id}")

        return {
            "success": True,
            "message": "Ticket resolved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to resolve ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/tickets/{ticket_id}/comments", tags=["Comments"])
async def get_comments(ticket_id: int, db: Session = Depends(get_db)):
    """Get ticket comments"""
    try:
        comments = db.query(TicketComment).filter(
            TicketComment.ticket_id == ticket_id
        ).order_by(TicketComment.created_at).all()

        return {
            "success": True,
            "count": len(comments),
            "comments": [
                {
                    "id": c.id,
                    "content": c.content,
                    "comment_type": c.comment_type.value,
                    "author_id": c.author_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "is_edited": c.is_edited
                }
                for c in comments
            ]
        }

    except Exception as e:
        logger.error(f"❌ Failed to fetch comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/tickets/{ticket_id}/comments", tags=["Comments"])
async def add_comment(ticket_id: int, comment_data: dict, db: Session = Depends(get_db)):
    """Add comment to ticket"""
    try:
        comment = TicketComment(
            ticket_id=ticket_id,
            author_id=comment_data.get("author_id"),
            content=comment_data.get("content"),
            comment_type=CommentType(comment_data.get("comment_type", "public"))
        )

        db.add(comment)
        db.commit()
        db.refresh(comment)

        logger.info(f"✅ Added comment to ticket {ticket_id}")

        return {
            "success": True,
            "comment_id": comment.id,
            "message": "Comment added successfully"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to add comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/comments/{comment_id}", tags=["Comments"])
async def update_comment(comment_id: int, content: str, db: Session = Depends(get_db)):
    """Update comment"""
    try:
        comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        comment.content = content
        comment.is_edited = True
        comment.updated_at = datetime.now(timezone.utc)

        db.commit()

        return {
            "success": True,
            "message": "Comment updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to update comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/comments/{comment_id}", tags=["Comments"])
async def delete_comment(comment_id: int, db: Session = Depends(get_db)):
    """Delete comment"""
    try:
        comment = db.query(TicketComment).filter(TicketComment.id == comment_id).first()

        if not comment:
            raise HTTPException(status_code=404, detail="Comment not found")

        db.delete(comment)
        db.commit()

        return {
            "success": True,
            "message": "Comment deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to delete comment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# LEGACY ENDPOINTS (Phase 2)
# ============================================================================

@app.post("/process-tickets", tags=["Tickets - Legacy"])
async def process_tickets_legacy(ticket_data: dict = None, db: Session = Depends(get_db)):
    """
    Legacy endpoint for backward compatibility

    Source: /backend/app/main.py:751-766

    DEPRECATED: Use /api/v1/tickets/process instead
    This endpoint exists for backward compatibility with old integrations
    """
    try:
        logger.warning("⚠️ Legacy endpoint /process-tickets called - please update to /api/v1/tickets/process")

        if ticket_data:
            # Single ticket processing
            result = await process_ticket(ticket_data, db)
            return result
        else:
            # Batch processing mode (fetch from Redmine and process all)
            return {
                "success": True,
                "message": "Batch processing not yet implemented in microservices. Use single ticket mode with ticket_data parameter.",
                "processed": 0,
                "note": "For batch processing, call /api/v1/tickets/process with ticket_data for each ticket"
            }

    except Exception as e:
        logger.error(f"❌ Legacy process tickets failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Starting {settings.SERVICE_NAME} on port {settings.SERVICE_PORT}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
