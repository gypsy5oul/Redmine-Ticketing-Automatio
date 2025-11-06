#!/usr/bin/env python3
"""
Escalation Service - Ticket escalation management

Port: 8007
Endpoints:
- POST /api/v1/escalations - Create escalation
- GET /api/v1/escalations/ticket/{id} - Get ticket escalations
- GET /api/v1/escalations/history - Get escalation history
"""

import os
import sys
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Add shared module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
from shared.auth_utils import setup_logging, log_request, get_current_user, User

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    SERVICE_NAME: str = "escalation-service"
    SERVICE_PORT: int = 8007

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

class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("ticket_history.id"), index=True)
    from_user_id = Column(Integer, ForeignKey("team_members.id"))
    to_user_id = Column(Integer, ForeignKey("team_members.id"))
    from_level = Column(String(10))
    to_level = Column(String(10))
    reason = Column(Text)
    escalated_at = Column(DateTime(timezone=True), server_default=func.now())

app = FastAPI(title="Escalation Service", version="1.0.0")

# Setup enhanced logging
logger = setup_logging("escalation-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

@app.post("/api/v1/escalations", tags=["Escalation"])
async def create_escalation(
    user: User = Depends(get_current_user),
    request: Request = None,
    data: dict = None,
    db: Session = Depends(get_db)
):
    """Create escalation - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "POST /api/v1/escalations")
    try:
        escalation = Escalation(
            ticket_id=data.get("ticket_id"),
            from_user_id=data.get("from_user_id"),
            to_user_id=data.get("to_user_id"),
            from_level=data.get("from_level"),
            to_level=data.get("to_level"),
            reason=data.get("reason", "")
        )
        db.add(escalation)
        db.commit()
        db.refresh(escalation)
        
        logger.info(f"✅ Escalation created: ticket {data.get('ticket_id')} from {data.get('from_level')} to {data.get('to_level')}")
        return {"success": True, "escalation_id": escalation.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/escalations/ticket/{ticket_id}", tags=["Escalation"])
async def get_ticket_escalations(
    ticket_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Get escalations for ticket - Requires: Any authenticated user"""
    log_request(logger, request, user.id, f"GET /api/v1/escalations/ticket/{ticket_id}")
    try:
        escalations = db.query(Escalation).filter(Escalation.ticket_id == ticket_id).all()
        return {
            "success": True,
            "count": len(escalations),
            "escalations": [
                {
                    "id": e.id,
                    "from_user_id": e.from_user_id,
                    "to_user_id": e.to_user_id,
                    "from_level": e.from_level,
                    "to_level": e.to_level,
                    "reason": e.reason,
                    "escalated_at": e.escalated_at.isoformat() if e.escalated_at else None
                }
                for e in escalations
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/escalations/history", tags=["Escalation"])
async def get_escalation_history(
    user: User = Depends(get_current_user),
    request: Request = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get escalation history - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/escalations/history")
    try:
        escalations = db.query(Escalation).order_by(Escalation.escalated_at.desc()).limit(limit).all()
        return {
            "success": True,
            "count": len(escalations),
            "history": [
                {
                    "ticket_id": e.ticket_id,
                    "from_level": e.from_level,
                    "to_level": e.to_level,
                    "escalated_at": e.escalated_at.isoformat() if e.escalated_at else None
                }
                for e in escalations
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
