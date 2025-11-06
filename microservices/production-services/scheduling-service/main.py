#!/usr/bin/env python3
"""
Scheduling Service - Shifts, leaves, on-call rotation management

Port: 8010
Endpoints:
- GET /api/v1/scheduling/shifts - List shifts
- POST /api/v1/scheduling/shifts - Create shift
- GET /api/v1/scheduling/leaves - List leaves
- POST /api/v1/scheduling/leaves - Request leave
"""

import os
from datetime import datetime, timezone, date
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Date, Time, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from loguru import logger

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    SERVICE_NAME: str = "scheduling-service"
    SERVICE_PORT: int = 8010

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

class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"))
    team_level = Column(String(10))
    day_of_week = Column(Integer)
    start_hour = Column(Integer)
    end_hour = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MemberLeave(Base):
    __tablename__ = "member_leaves"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"))
    leave_type = Column(String(50))
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(50), default="pending")
    reason = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

app = FastAPI(title="Scheduling Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

@app.get("/api/v1/scheduling/shifts", tags=["Scheduling"])
async def get_shifts(member_id: int = None, db: Session = Depends(get_db)):
    """Get shift assignments"""
    try:
        query = db.query(ShiftAssignment).filter(ShiftAssignment.is_active == True)
        if member_id:
            query = query.filter(ShiftAssignment.team_member_id == member_id)
        
        shifts = query.all()
        return {
            "success": True,
            "count": len(shifts),
            "shifts": [
                {
                    "id": s.id,
                    "team_member_id": s.team_member_id,
                    "day_of_week": s.day_of_week,
                    "start_hour": s.start_hour,
                    "end_hour": s.end_hour
                }
                for s in shifts
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/scheduling/shifts", tags=["Scheduling"])
async def create_shift(data: dict, db: Session = Depends(get_db)):
    """Create shift assignment"""
    try:
        shift = ShiftAssignment(
            team_member_id=data.get("team_member_id"),
            team_level=data.get("team_level"),
            day_of_week=data.get("day_of_week"),
            start_hour=data.get("start_hour"),
            end_hour=data.get("end_hour")
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)
        
        logger.info(f"✅ Shift created for member {data.get('team_member_id')}")
        return {"success": True, "shift_id": shift.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/scheduling/leaves", tags=["Scheduling"])
async def get_leaves(member_id: int = None, db: Session = Depends(get_db)):
    """Get leave requests"""
    try:
        query = db.query(MemberLeave)
        if member_id:
            query = query.filter(MemberLeave.team_member_id == member_id)
        
        leaves = query.order_by(MemberLeave.created_at.desc()).all()
        return {
            "success": True,
            "count": len(leaves),
            "leaves": [
                {
                    "id": l.id,
                    "team_member_id": l.team_member_id,
                    "leave_type": l.leave_type,
                    "start_date": l.start_date.isoformat() if l.start_date else None,
                    "end_date": l.end_date.isoformat() if l.end_date else None,
                    "status": l.status
                }
                for l in leaves
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/scheduling/leaves", tags=["Scheduling"])
async def request_leave(data: dict, db: Session = Depends(get_db)):
    """Request leave"""
    try:
        leave = MemberLeave(
            team_member_id=data.get("team_member_id"),
            leave_type=data.get("leave_type"),
            start_date=datetime.fromisoformat(data.get("start_date")).date(),
            end_date=datetime.fromisoformat(data.get("end_date")).date(),
            reason=data.get("reason", "")
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)
        
        logger.info(f"✅ Leave requested by member {data.get('team_member_id')}")
        return {"success": True, "leave_id": leave.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
