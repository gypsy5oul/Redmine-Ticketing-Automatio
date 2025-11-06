"""
Team Service - Microservice for team member management

Extracted from main.py lines ~2398-2961
Handles: Team members, skills, performance tracking
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from loguru import logger
import os

# Import shared utilities
import sys
sys.path.append('../../shared')

from database import get_db, engine
from auth import get_current_user_id

# Import models from original app (shared database)
# In production, you'd import from your shared package
sys.path.append('../../../backend')
from app.models.team import TeamMember, TeamLevel
from app.models.user import User, UserRole
from app.models.ticket import TicketHistory, TicketStatus

# Initialize FastAPI app
app = FastAPI(
    title="Team Service",
    version="1.0.0",
    description="Team member management microservice"
)

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Schemas
# ============================================================================

class TeamMemberResponse(BaseModel):
    """Team member response schema"""
    id: int
    redmine_user_id: int
    name: str
    email: str
    team_level: str
    max_tickets: int
    active: bool
    skills: Optional[List[str]]
    shift_start: Optional[str]
    shift_end: Optional[str]

    class Config:
        from_attributes = True


class TeamMemberCreate(BaseModel):
    """Create team member request"""
    redmine_user_id: int
    name: str = Field(..., min_length=2)
    email: str
    team_level: TeamLevel
    max_tickets: int = Field(default=5, ge=1, le=20)
    skills: Optional[List[str]] = None


class TeamMemberUpdate(BaseModel):
    """Update team member request"""
    name: Optional[str] = None
    email: Optional[str] = None
    team_level: Optional[TeamLevel] = None
    max_tickets: Optional[int] = Field(None, ge=1, le=20)
    active: Optional[bool] = None
    skills: Optional[List[str]] = None


class PerformanceMetrics(BaseModel):
    """Team member performance metrics"""
    member_id: int
    member_name: str
    total_tickets: int
    resolved_tickets: int
    avg_resolution_hours: float
    sla_compliance_rate: float
    current_workload: int


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "team-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Team Members CRUD
# ============================================================================

@app.get("/team/members", response_model=List[TeamMemberResponse])
async def get_team_members(
    active: bool = Query(default=True, description="Filter by active status"),
    team_level: Optional[str] = Query(None, description="Filter by team level"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Get all team members

    Extracted from main.py line 2398
    """
    try:
        query = db.query(TeamMember)

        if active is not None:
            query = query.filter(TeamMember.active == active)

        if team_level:
            query = query.filter(TeamMember.team_level == team_level)

        members = query.all()

        logger.info(f"Retrieved {len(members)} team members")

        return members

    except Exception as e:
        logger.error(f"Error fetching team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/team/members/{member_id}", response_model=TeamMemberResponse)
async def get_team_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Get team member by ID

    Extracted from main.py line 2457
    """
    member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

    if not member:
        raise HTTPException(status_code=404, detail=f"Team member {member_id} not found")

    return member


@app.post("/team/members", response_model=TeamMemberResponse, status_code=201)
async def create_team_member(
    member_data: TeamMemberCreate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Create new team member

    Extracted from main.py line 2496
    Requires: Admin role (TODO: Add role check via shared auth)
    """
    try:
        # Check if redmine_user_id already exists
        existing = db.query(TeamMember).filter(
            TeamMember.redmine_user_id == member_data.redmine_user_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Team member with Redmine ID {member_data.redmine_user_id} already exists"
            )

        # Create new team member
        new_member = TeamMember(
            redmine_user_id=member_data.redmine_user_id,
            name=member_data.name,
            email=member_data.email,
            team_level=member_data.team_level,
            max_tickets=member_data.max_tickets,
            skills=member_data.skills or [],
            active=True
        )

        db.add(new_member)
        db.commit()
        db.refresh(new_member)

        logger.info(f"Created team member: {new_member.name}")

        return new_member

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/team/members/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: int,
    member_data: TeamMemberUpdate,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Update team member

    Extracted from main.py line 2649
    """
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail=f"Team member {member_id} not found")

        # Update fields
        if member_data.name is not None:
            member.name = member_data.name

        if member_data.email is not None:
            member.email = member_data.email

        if member_data.team_level is not None:
            member.team_level = member_data.team_level

        if member_data.max_tickets is not None:
            member.max_tickets = member_data.max_tickets

        if member_data.active is not None:
            member.active = member_data.active

        if member_data.skills is not None:
            member.skills = member_data.skills

        db.commit()
        db.refresh(member)

        logger.info(f"Updated team member: {member.name}")

        return member

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/team/members/{member_id}", status_code=204)
async def delete_team_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Delete (deactivate) team member

    Extracted from main.py line 2718
    """
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail=f"Team member {member_id} not found")

        # Soft delete (deactivate)
        member.active = False
        db.commit()

        logger.info(f"Deactivated team member: {member.name}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Performance Metrics
# ============================================================================

@app.get("/team/members/{member_id}/performance", response_model=PerformanceMetrics)
async def get_member_performance(
    member_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Get performance metrics for a team member

    Extracted from main.py line 2748
    """
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail=f"Team member {member_id} not found")

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get tickets assigned to this member in the period
        tickets = db.query(TicketHistory).filter(
            TicketHistory.assigned_to_id == member_id,
            TicketHistory.assigned_at >= start_date
        ).all()

        # Calculate metrics
        total_tickets = len(tickets)
        resolved_tickets = sum(1 for t in tickets if t.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED])

        # Average resolution time
        resolved_with_time = [t for t in tickets if t.actual_resolution_hours]
        avg_resolution_hours = (
            sum(t.actual_resolution_hours for t in resolved_with_time) / len(resolved_with_time)
            if resolved_with_time else 0
        )

        # SLA compliance
        sla_met = sum(1 for t in tickets if not t.sla_breached and t.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED])
        sla_compliance_rate = (sla_met / resolved_tickets * 100) if resolved_tickets > 0 else 100

        # Current workload
        current_workload = db.query(TicketHistory).filter(
            TicketHistory.assigned_to_id == member_id,
            TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
        ).count()

        return {
            "member_id": member.id,
            "member_name": member.name,
            "total_tickets": total_tickets,
            "resolved_tickets": resolved_tickets,
            "avg_resolution_hours": round(avg_resolution_hours, 2),
            "sla_compliance_rate": round(sla_compliance_rate, 1),
            "current_workload": current_workload
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Skills Management
# ============================================================================

@app.get("/team/skills")
async def get_all_skills(
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Get all unique skills across team members

    Extracted from main.py line 2264
    """
    try:
        members = db.query(TeamMember).filter(TeamMember.active == True).all()

        # Collect all unique skills
        all_skills = set()
        for member in members:
            if member.skills:
                all_skills.update(member.skills)

        return {
            "skills": sorted(list(all_skills)),
            "total_skills": len(all_skills)
        }

    except Exception as e:
        logger.error(f"Error fetching skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/team/skills")
async def update_member_skills(
    member_id: int,
    skills: List[str],
    db: Session = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id)
):
    """
    Update skills for a team member

    Extracted from main.py line 2290
    """
    try:
        member = db.query(TeamMember).filter(TeamMember.id == member_id).first()

        if not member:
            raise HTTPException(status_code=404, detail=f"Team member {member_id} not found")

        member.skills = skills
        db.commit()

        logger.info(f"Updated skills for {member.name}: {skills}")

        return {
            "member_id": member.id,
            "name": member.name,
            "skills": member.skills
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating skills: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("🚀 Starting Team Service v1.0.0")
    logger.info("✅ Team Service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down Team Service...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
