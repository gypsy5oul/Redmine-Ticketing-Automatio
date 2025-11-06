#!/usr/bin/env python3
"""
Analytics & ML Service - ML predictions, forecasting, dashboards

Port: 8006
Endpoints:
- GET /api/v1/analytics/dashboard - Get dashboard metrics
- GET /api/v1/analytics/trends - Get trend analysis
- GET /api/v1/analytics/performance - Get team performance
- POST /api/v1/ml/predict-category - Predict ticket category
- POST /api/v1/ml/predict-effort - Predict resolution time
- GET /api/v1/ml/forecast - Forecast ticket volume
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, ForeignKey, func, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from loguru import logger

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://ticketing_user:securepassword@localhost:5432/ticketing_db")
    SERVICE_NAME: str = "analytics-service"
    SERVICE_PORT: int = 8006

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

class TicketHistory(Base):
    __tablename__ = "ticket_history"
    id = Column(Integer, primary_key=True)
    redmine_ticket_id = Column(Integer)
    subject = Column(String(500))
    priority = Column(String(50))
    status = Column(String(50))
    category = Column(String(50))
    assigned_to_id = Column(Integer)
    sla_breached = Column(Boolean)
    created_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))

class TeamMember(Base):
    __tablename__ = "team_members"
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    team_level = Column(String(10))
    total_tickets_resolved = Column(Integer, default=0)
    sla_compliance_rate = Column(Float, default=100.0)
    avg_resolution_time_hours = Column(Float, default=0.0)

class SimpleLLMPredictor:
    """Simple rule-based predictor (fallback when ML not available)"""

    def predict_category(self, subject: str, description: str) -> Dict:
        """Predict ticket category"""
        text = f"{subject} {description}".lower()

        keywords = {
            'kubernetes': ['k8s', 'kubernetes', 'pod', 'deployment', 'helm'],
            'database': ['database', 'postgres', 'mysql', 'sql', 'query'],
            'network': ['network', 'firewall', 'dns', 'ip', 'route'],
            'cicd': ['gitlab', 'jenkins', 'pipeline', 'deploy', 'build'],
            'messaging': ['rabbitmq', 'kafka', 'queue', 'message']
        }

        for category, words in keywords.items():
            if any(word in text for word in words):
                return {"category": category, "confidence": 0.75}

        return {"category": "other", "confidence": 0.5}

    def predict_effort(self, category: str, priority: str) -> Dict:
        """Predict resolution effort"""
        effort_map = {
            'P1(Critical)': 4.0,
            'P2(High)': 8.0,
            'P3(Medium)': 12.0,
            'P4(Low)': 24.0,
            'P5(Trivial)': 48.0
        }

        hours = effort_map.get(priority, 12.0)

        # Adjust by category complexity
        if category in ['kubernetes', 'database']:
            hours *= 1.5

        return {"estimated_hours": hours, "confidence": 0.65}

app = FastAPI(title="Analytics & ML Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health_check():
    return {"service": settings.SERVICE_NAME, "status": "healthy"}

@app.get("/api/v1/analytics/dashboard", tags=["Analytics"])
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard metrics"""
    try:
        # Total tickets
        total_tickets = db.query(TicketHistory).count()

        # Open tickets
        open_tickets = db.query(TicketHistory).filter(
            TicketHistory.status.in_(["new", "assigned", "in_progress"])
        ).count()

        # SLA breaches
        sla_breached = db.query(TicketHistory).filter(
            TicketHistory.sla_breached == True
        ).count()

        # Avg resolution time
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

@app.get("/api/v1/analytics/trends", tags=["Analytics"])
async def get_trends(days: int = 30, db: Session = Depends(get_db)):
    """Get trend analysis"""
    try:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        tickets = db.query(TicketHistory).filter(
            TicketHistory.created_at >= start_date
        ).all()

        # Group by day
        daily_counts = {}
        for ticket in tickets:
            if ticket.created_at:
                day = ticket.created_at.date().isoformat()
                daily_counts[day] = daily_counts.get(day, 0) + 1

        trend_data = [
            {"date": date, "count": count}
            for date, count in sorted(daily_counts.items())
        ]

        return {
            "success": True,
            "period_days": days,
            "total_tickets": len(tickets),
            "trends": trend_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/analytics/performance", tags=["Analytics"])
async def get_performance(db: Session = Depends(get_db)):
    """Get team performance"""
    try:
        members = db.query(TeamMember).all()

        performance_data = [
            {
                "member_id": m.id,
                "name": m.name,
                "team_level": m.team_level,
                "total_resolved": m.total_tickets_resolved,
                "sla_compliance_rate": m.sla_compliance_rate,
                "avg_resolution_hours": m.avg_resolution_time_hours
            }
            for m in members
        ]

        # Sort by performance score
        performance_data.sort(
            key=lambda x: (x['sla_compliance_rate'], x['total_resolved']),
            reverse=True
        )

        return {
            "success": True,
            "count": len(performance_data),
            "performance": performance_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ml/predict-category", tags=["ML"])
async def predict_category(data: dict):
    """Predict ticket category using ML"""
    try:
        predictor = SimpleLLMPredictor()
        result = predictor.predict_category(
            data.get("subject", ""),
            data.get("description", "")
        )

        return {"success": True, "prediction": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/ml/predict-effort", tags=["ML"])
async def predict_effort(data: dict):
    """Predict resolution effort"""
    try:
        predictor = SimpleLLMPredictor()
        result = predictor.predict_effort(
            data.get("category", "other"),
            data.get("priority", "P3(Medium)")
        )

        return {"success": True, "prediction": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/ml/forecast", tags=["ML"])
async def forecast_volume(days: int = 7, db: Session = Depends(get_db)):
    """Forecast ticket volume"""
    try:
        # Simple moving average forecast
        lookback_days = 30
        start_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        historical = db.query(TicketHistory).filter(
            TicketHistory.created_at >= start_date
        ).count()

        daily_avg = historical / lookback_days
        forecast = daily_avg * days

        return {
            "success": True,
            "forecast_days": days,
            "estimated_tickets": round(forecast),
            "daily_average": round(daily_avg, 2),
            "method": "moving_average"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
