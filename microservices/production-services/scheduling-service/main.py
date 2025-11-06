#!/usr/bin/env python3
"""
Scheduling Service - Shifts, leaves, on-call rotation + Background Job Scheduler

Port: 8010
Features:
- Shift management
- Leave management
- Background scheduler with APScheduler (9 jobs from old app)

Source: /backend/app/scheduler/scheduler.py
"""

import os
import sys
import httpx
from datetime import datetime, timezone, date, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Date, Time, func, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

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

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://devops_user:devops_password_change_this@postgres:5432/devops_tickets")
    SERVICE_NAME: str = "scheduling-service"
    SERVICE_PORT: int = 8010

    # API Gateway base URL for inter-service communication
    API_GATEWAY_URL: str = os.getenv("API_GATEWAY_URL", "http://kong-gateway:8000")

    # Job intervals (in minutes)
    TICKET_PROCESSING_INTERVAL: int = int(os.getenv("TICKET_PROCESSING_INTERVAL", "2"))
    SLA_CHECK_INTERVAL: int = int(os.getenv("SLA_CHECK_INTERVAL", "1"))
    REDMINE_STATUS_SYNC_INTERVAL: int = int(os.getenv("REDMINE_STATUS_SYNC_INTERVAL", "5"))

settings = Settings()

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize APScheduler
scheduler = AsyncIOScheduler()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# DATABASE MODELS
# ============================================================================

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

class OnCallAssignment(Base):
    __tablename__ = "oncall_assignments"
    id = Column(Integer, primary_key=True)
    team_member_id = Column(Integer, ForeignKey("team_members.id"), nullable=True)
    team_level = Column(String(10), nullable=False)
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SchedulerJobLog(Base):
    """Track scheduler job executions"""
    __tablename__ = "scheduler_job_logs"
    id = Column(Integer, primary_key=True)
    job_id = Column(String(100), nullable=False, index=True)
    job_name = Column(String(200), nullable=False)
    status = Column(String(50), nullable=False)  # success, failed
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    result_message = Column(Text)
    error_message = Column(Text)

# ============================================================================
# BACKGROUND JOB DEFINITIONS
# ============================================================================

async def process_new_tickets_job():
    """
    JOB 1: Process new tickets from Redmine
    Source: /backend/app/scheduler/scheduler.py:24-42
    Interval: Every 2 minutes (configurable)
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("🔄 [Job 1/9] Running scheduled ticket processing...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.API_GATEWAY_URL}/api/v1/tickets/process",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                message = f"Processed: {result.get('processed', 0)}, Assigned: {result.get('assigned', 0)}"
                logger.info(f"✅ Scheduled ticket processing complete: {message}")

                log = SchedulerJobLog(
                    job_id="process_tickets",
                    job_name="Process New Tickets",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ Scheduled ticket processing failed: {e}")
        log = SchedulerJobLog(
            job_id="process_tickets",
            job_name="Process New Tickets",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def check_sla_status_job():
    """
    JOB 2: Check and update SLA status for all active tickets
    Source: /backend/app/scheduler/scheduler.py:45-64
    Interval: Every 1 minute (configurable)
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("⏱️  [Job 2/9] Running scheduled SLA checks...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all at-risk tickets to trigger SLA calculation
            response = await client.get(
                f"{settings.API_GATEWAY_URL}/api/v1/sla/at-risk",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                at_risk_count = result.get('count', 0)
                message = f"Checked SLA status, {at_risk_count} tickets at risk"
                logger.info(f"✅ SLA check complete: {message}")

                log = SchedulerJobLog(
                    job_id="check_sla",
                    job_name="Check SLA Status",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ SLA check job failed: {e}")
        log = SchedulerJobLog(
            job_id="check_sla",
            job_name="Check SLA Status",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def update_workload_cache_job():
    """
    JOB 3: Update workload cache for all team members
    Source: /backend/app/scheduler/scheduler.py:67-86
    Interval: Every 5 minutes
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.debug("♻️  [Job 3/9] Updating workload cache...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all team members
            response = await client.get(
                f"{settings.API_GATEWAY_URL}/api/v1/team/members",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                members = result.get('members', [])

                # Update workload for each member
                updated_count = 0
                for member in members:
                    if member.get('active'):
                        try:
                            workload_response = await client.get(
                                f"{settings.API_GATEWAY_URL}/api/v1/workload/{member['id']}",
                                headers={"Content-Type": "application/json"}
                            )
                            if workload_response.status_code == 200:
                                updated_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to update workload for member {member['id']}: {e}")

                message = f"Updated workload cache for {updated_count}/{len(members)} members"
                logger.debug(f"✅ {message}")

                log = SchedulerJobLog(
                    job_id="update_workload",
                    job_name="Update Workload Cache",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ Workload cache update failed: {e}")
        log = SchedulerJobLog(
            job_id="update_workload",
            job_name="Update Workload Cache",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def send_daily_summary_job():
    """
    JOB 4: Send daily performance summary
    Source: /backend/app/scheduler/scheduler.py:89-152
    Schedule: Daily at 9:00 AM
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("📊 [Job 4/9] Generating daily summary...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get dashboard metrics which includes daily stats
            response = await client.get(
                f"{settings.API_GATEWAY_URL}/api/v1/analytics/dashboard",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                message = f"Daily summary generated with {result.get('total_tickets', 0)} total tickets"
                logger.info(f"✅ Daily summary sent: {message}")

                log = SchedulerJobLog(
                    job_id="daily_summary",
                    job_name="Send Daily Summary",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ Daily summary job failed: {e}")
        log = SchedulerJobLog(
            job_id="daily_summary",
            job_name="Send Daily Summary",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def check_capacity_alerts_job():
    """
    JOB 5: Check for capacity alerts and send notifications
    Source: /backend/app/scheduler/scheduler.py:155-172
    Interval: Every 30 minutes
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.debug("🔔 [Job 5/9] Checking capacity alerts...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check workload distribution
            response = await client.get(
                f"{settings.API_GATEWAY_URL}/api/v1/workload/distribution",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                overloaded = [m for m in result.get('members', []) if m.get('workload_percentage', 0) > 90]

                message = f"Capacity check complete, {len(overloaded)} overloaded members"
                if overloaded:
                    logger.warning(f"⚠️ {message}")
                else:
                    logger.debug(f"✅ {message}")

                log = SchedulerJobLog(
                    job_id="capacity_alerts",
                    job_name="Check Capacity Alerts",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ Capacity alerts job failed: {e}")
        log = SchedulerJobLog(
            job_id="capacity_alerts",
            job_name="Check Capacity Alerts",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def retrain_ml_models_job():
    """
    JOB 6: Retrain ML models with latest historical data
    Source: /backend/app/scheduler/scheduler.py:175-198
    Schedule: Weekly on Sunday at 2:00 AM
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("🎓 [Job 6/9] Running scheduled ML model retraining...")

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Trigger ML model training
            response = await client.post(
                f"{settings.API_GATEWAY_URL}/api/v1/analytics/ml/train",
                headers={"Content-Type": "application/json"},
                json={"force_retrain": False}
            )

            if response.status_code == 200:
                result = response.json()
                message = f"ML models retrained: {result.get('training_samples', 0)} samples"
                logger.info(f"✅ {message}")

                log = SchedulerJobLog(
                    job_id="ml_retraining",
                    job_name="Retrain ML Models",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ ML retraining job failed: {e}")
        log = SchedulerJobLog(
            job_id="ml_retraining",
            job_name="Retrain ML Models",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def sync_redmine_statuses_job():
    """
    JOB 7: Synchronize ticket statuses with Redmine
    Source: /backend/app/scheduler/scheduler.py:237-257
    Interval: Every 5 minutes (configurable)
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("🔄 [Job 7/9] Syncing ticket statuses with Redmine...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Trigger Redmine sync
            response = await client.post(
                f"{settings.API_GATEWAY_URL}/api/v1/integration/redmine/sync-statuses",
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                message = f"Synced: {result.get('updated', 0)} updated, {result.get('closed', 0)} closed"
                logger.info(f"✅ Redmine sync complete: {message}")

                log = SchedulerJobLog(
                    job_id="redmine_status_sync",
                    job_name="Sync Redmine Ticket Statuses",
                    status="success",
                    started_at=job_start,
                    completed_at=datetime.now(timezone.utc),
                    duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
                    result_message=message
                )
                db.add(log)
                db.commit()
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"❌ Redmine sync job failed: {e}")
        log = SchedulerJobLog(
            job_id="redmine_status_sync",
            job_name="Sync Redmine Ticket Statuses",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def ensure_standard_shifts_job():
    """
    JOB 8: Ensure default weekday shifts exist for all members
    Source: /backend/app/scheduler/scheduler.py:201-213
    Schedule: Daily at 6:00 AM
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("📅 [Job 8/9] Ensuring standard shifts...")

        from sqlalchemy import and_

        # Get all active team members
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        result = db.execute(
            team_members.select().where(team_members.c.active == True)
        )
        members = result.fetchall()

        created_count = 0
        # Ensure weekday shifts (Monday=0 to Friday=4) for all members
        for member in members:
            for day in range(5):  # Monday to Friday
                # Check if shift exists
                existing = db.query(ShiftAssignment).filter(
                    and_(
                        ShiftAssignment.team_member_id == member.id,
                        ShiftAssignment.day_of_week == day,
                        ShiftAssignment.is_active == True
                    )
                ).first()

                if not existing:
                    # Create default 9-5 shift
                    shift = ShiftAssignment(
                        team_member_id=member.id,
                        team_level=member.team_level,
                        day_of_week=day,
                        start_hour=9,
                        end_hour=17,
                        is_active=True
                    )
                    db.add(shift)
                    created_count += 1

        if created_count > 0:
            db.commit()

        message = f"Standard shifts ensured: {created_count} shifts created"
        logger.info(f"✅ {message}")

        log = SchedulerJobLog(
            job_id="ensure_standard_shifts",
            job_name="Ensure Standard Shifts",
            status="success",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            result_message=message
        )
        db.add(log)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Standard shift job failed: {e}")
        log = SchedulerJobLog(
            job_id="ensure_standard_shifts",
            job_name="Ensure Standard Shifts",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


async def assign_oncall_roster_job():
    """
    JOB 9: Prepare the weekly on-call roster and notify teams
    Source: /backend/app/scheduler/scheduler.py:216-234
    Schedule: Monday at 8:00 AM
    """
    job_start = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        logger.info("👥 [Job 9/9] Preparing on-call roster...")

        from sqlalchemy import Table, MetaData, and_
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        # Get week boundaries (Monday to Sunday)
        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # This Monday
        week_end = week_start + timedelta(days=6)  # This Sunday

        # Check if roster already exists for this week
        existing = db.query(OnCallAssignment).filter(
            and_(
                OnCallAssignment.week_start == week_start,
                OnCallAssignment.is_active == True
            )
        ).first()

        if existing:
            message = f"On-call roster already exists for week {week_start}"
            logger.info(f"⚠️ {message}")
        else:
            # Assign L2 and L3 members for on-call
            assignments_created = []

            for level in ['L2', 'L3']:
                # Get available members for this level
                result = db.execute(
                    team_members.select().where(
                        and_(
                            team_members.c.active == True,
                            team_members.c.team_level == level
                        )
                    )
                )
                members = result.fetchall()

                if members:
                    # Simple round-robin: pick first available
                    # In production, implement more sophisticated rotation logic
                    selected_member = members[0]

                    assignment = OnCallAssignment(
                        team_member_id=selected_member.id,
                        team_level=level,
                        week_start=week_start,
                        week_end=week_end,
                        is_active=True
                    )
                    db.add(assignment)
                    assignments_created.append(f"{level}: {selected_member.name}")

            db.commit()
            message = f"On-call roster created for week {week_start}: {', '.join(assignments_created)}"
            logger.info(f"✅ {message}")

        log = SchedulerJobLog(
            job_id="assign_oncall_roster",
            job_name="Assign On-Call Roster",
            status="success",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            result_message=message
        )
        db.add(log)
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"❌ On-call roster job failed: {e}")
        log = SchedulerJobLog(
            job_id="assign_oncall_roster",
            job_name="Assign On-Call Roster",
            status="failed",
            started_at=job_start,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - job_start).seconds,
            error_message=str(e)
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


# ============================================================================
# SCHEDULER MANAGEMENT
# ============================================================================

def start_scheduler():
    """
    Start the background scheduler with all 9 jobs
    Source: /backend/app/scheduler/scheduler.py:264-369
    """
    try:
        # Job 1: Process new tickets every 2 minutes
        scheduler.add_job(
            process_new_tickets_job,
            trigger=IntervalTrigger(minutes=settings.TICKET_PROCESSING_INTERVAL),
            id='process_tickets',
            name='Process New Tickets',
            replace_existing=True,
            max_instances=1
        )

        # Job 2: Check SLA status every 1 minute
        scheduler.add_job(
            check_sla_status_job,
            trigger=IntervalTrigger(minutes=settings.SLA_CHECK_INTERVAL),
            id='check_sla',
            name='Check SLA Status',
            replace_existing=True,
            max_instances=1
        )

        # Job 3: Update workload cache every 5 minutes
        scheduler.add_job(
            update_workload_cache_job,
            trigger=IntervalTrigger(minutes=5),
            id='update_workload',
            name='Update Workload Cache',
            replace_existing=True,
            max_instances=1
        )

        # Job 4: Send daily summary at 9 AM
        scheduler.add_job(
            send_daily_summary_job,
            trigger=CronTrigger(hour=9, minute=0),
            id='daily_summary',
            name='Send Daily Summary',
            replace_existing=True
        )

        # Job 5: Check capacity alerts every 30 minutes
        scheduler.add_job(
            check_capacity_alerts_job,
            trigger=IntervalTrigger(minutes=30),
            id='capacity_alerts',
            name='Check Capacity Alerts',
            replace_existing=True,
            max_instances=1
        )

        # Job 6: Retrain ML models weekly (Sunday at 2 AM)
        scheduler.add_job(
            retrain_ml_models_job,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='ml_retraining',
            name='Retrain ML Models',
            replace_existing=True
        )

        # Job 7: Sync ticket statuses with Redmine
        scheduler.add_job(
            sync_redmine_statuses_job,
            trigger=IntervalTrigger(minutes=settings.REDMINE_STATUS_SYNC_INTERVAL),
            id='redmine_status_sync',
            name='Sync Redmine Ticket Statuses',
            replace_existing=True,
            max_instances=1
        )

        # Job 8: Ensure default shifts daily at 6 AM
        scheduler.add_job(
            ensure_standard_shifts_job,
            trigger=CronTrigger(hour=6, minute=0),
            id='ensure_standard_shifts',
            name='Ensure Standard Shifts',
            replace_existing=True,
            max_instances=1
        )

        # Job 9: Assign on-call roster Monday at 8 AM
        scheduler.add_job(
            assign_oncall_roster_job,
            trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='assign_oncall_roster',
            name='Assign On-Call Roster',
            replace_existing=True,
            max_instances=1
        )

        scheduler.start()
        logger.info("✅ Background scheduler started with 9 jobs")
        logger.info(f"   1. Process tickets: every {settings.TICKET_PROCESSING_INTERVAL} minutes")
        logger.info(f"   2. Check SLA: every {settings.SLA_CHECK_INTERVAL} minute(s)")
        logger.info(f"   3. Update workload: every 5 minutes")
        logger.info(f"   4. Daily summary: daily at 9:00 AM")
        logger.info(f"   5. Capacity alerts: every 30 minutes")
        logger.info(f"   6. ML retraining: weekly on Sunday at 2:00 AM")
        logger.info(f"   7. Redmine sync: every {settings.REDMINE_STATUS_SYNC_INTERVAL} minutes")
        logger.info(f"   8. Ensure standard shifts: daily at 06:00 AM")
        logger.info(f"   9. On-call roster: Mondays at 08:00 AM")

    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown()
        logger.info("✅ Background scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop scheduler: {e}")


# ============================================================================
# FASTAPI APPLICATION WITH LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage scheduler lifecycle"""
    # Startup: Create tables and start scheduler
    logger.info("🚀 Starting scheduling service...")
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    # Shutdown: Stop scheduler
    stop_scheduler()


app = FastAPI(
    title="Scheduling Service with Background Jobs",
    version="1.0.0",
    lifespan=lifespan
)

# Setup enhanced logging with request tracking
logger = setup_logging("scheduling-service", os.getenv("LOG_LEVEL", "INFO"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    return {
        "service": settings.SERVICE_NAME,
        "status": "healthy",
        "scheduler_running": scheduler.running if scheduler else False
    }


@app.get("/api/v1/scheduler/status", tags=["Scheduler"])
async def get_scheduler_status():
    """
    Get status of background scheduler jobs
    Source: /backend/app/main.py:2891-2921
    """
    try:
        if not scheduler or not scheduler.running:
            return {
                "running": False,
                "jobs": [],
                "total_jobs": 0,
                "message": "Scheduler not running"
            }

        jobs = scheduler.get_jobs()
        return {
            "running": True,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger)
                }
                for job in jobs
            ],
            "total_jobs": len(jobs)
        }
    except Exception as e:
        logger.error(f"❌ Failed to get scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/scheduler/logs", tags=["Scheduler"])
async def get_scheduler_logs(limit: int = 50, job_id: str = None, db: Session = Depends(get_db)):
    """Get recent scheduler job execution logs"""
    try:
        query = db.query(SchedulerJobLog).order_by(SchedulerJobLog.started_at.desc())

        if job_id:
            query = query.filter(SchedulerJobLog.job_id == job_id)

        logs = query.limit(limit).all()

        return {
            "success": True,
            "count": len(logs),
            "logs": [
                {
                    "id": log.id,
                    "job_id": log.job_id,
                    "job_name": log.job_name,
                    "status": log.status,
                    "started_at": log.started_at.isoformat(),
                    "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                    "duration_seconds": log.duration_seconds,
                    "result_message": log.result_message,
                    "error_message": log.error_message
                }
                for log in logs
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/api/v1/scheduling/oncall", tags=["Scheduling"])
async def get_oncall_roster(week_start: date = None, db: Session = Depends(get_db)):
    """Get on-call roster for a specific week"""
    try:
        if not week_start:
            # Get current week
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        assignments = db.query(OnCallAssignment).filter(
            OnCallAssignment.week_start == week_start,
            OnCallAssignment.is_active == True
        ).all()

        return {
            "success": True,
            "week_start": week_start.isoformat(),
            "count": len(assignments),
            "assignments": [
                {
                    "id": a.id,
                    "team_member_id": a.team_member_id,
                    "team_level": a.team_level,
                    "week_start": a.week_start.isoformat(),
                    "week_end": a.week_end.isoformat()
                }
                for a in assignments
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FRONTEND-COMPATIBLE ENDPOINTS (All /api/v1/* paths)
# These endpoints match what the frontend expects
# ============================================================================

from typing import Optional
from pydantic import BaseModel
from fastapi import Query

# Pydantic models for request validation
class ShiftCreateRequest(BaseModel):
    team_member_id: int
    team_level: Optional[str] = None
    day_of_week: Optional[int] = None
    start_hour: int = 9
    start_minute: int = 0
    end_hour: int = 17
    end_minute: int = 0
    timezone: str = "Asia/Kolkata"
    priority: int = 50
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None

class ShiftUpdateRequest(BaseModel):
    team_member_id: Optional[int] = None
    team_level: Optional[str] = None
    day_of_week: Optional[int] = None
    start_hour: Optional[int] = None
    start_minute: Optional[int] = None
    end_hour: Optional[int] = None
    end_minute: Optional[int] = None
    timezone: Optional[str] = None
    priority: Optional[int] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class LeaveCreateRequest(BaseModel):
    team_member_id: Optional[int] = None
    start_date: str
    end_date: str
    leave_type: str = "vacation"
    reason: Optional[str] = None

class LeaveUpdateRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    leave_type: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None

class OnCallRunRequest(BaseModel):
    week_start: Optional[str] = None
    force: bool = False

class OnCallReplaceRequest(BaseModel):
    team_member_id: int
    reason: Optional[str] = None


# ============================================================================
# SHIFTS ENDPOINTS
# ============================================================================

@app.get("/api/v1/shifts", tags=["Shifts"])
async def get_shifts_v1(
    user: User = Depends(require_manager),
    request: Request = None,
    team_level: Optional[str] = Query(None),
    member_id: Optional[int] = Query(None),
    include_inactive: bool = Query(False),
    grouped: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Get shift assignments
    Supports grouped view for frontend
    Requires: Manager, Admin, or Super Admin role
    """
    log_request(logger, request, user.id, "GET /api/v1/shifts")
    try:
        from sqlalchemy import Table, MetaData, and_

        query = db.query(ShiftAssignment)

        if not include_inactive:
            query = query.filter(ShiftAssignment.is_active == True)

        if member_id:
            query = query.filter(ShiftAssignment.team_member_id == member_id)

        if team_level:
            query = query.filter(ShiftAssignment.team_level == team_level)

        shifts = query.all()

        if grouped:
            # Group shifts by team member
            metadata = MetaData()
            team_members = Table('team_members', metadata, autoload_with=engine)

            grouped_data = {}
            for shift in shifts:
                mid = shift.team_member_id
                if mid not in grouped_data:
                    # Get team member info
                    member_result = db.execute(
                        team_members.select().where(team_members.c.id == mid)
                    ).first()

                    grouped_data[mid] = {
                        "id": mid,
                        "team_member_id": mid,
                        "team_member_name": member_result.name if member_result else f"Member {mid}",
                        "team_level": member_result.team_level if member_result else shift.team_level,
                        "timezone": "Asia/Kolkata",
                        "is_active": shift.is_active,
                        "shifts": []
                    }

                grouped_data[mid]["shifts"].append({
                    "id": shift.id,
                    "team_member_id": shift.team_member_id,
                    "team_level": shift.team_level,
                    "day_of_week": shift.day_of_week,
                    "start_hour": shift.start_hour,
                    "start_minute": 0,
                    "end_hour": shift.end_hour,
                    "end_minute": 0,
                    "timezone": "Asia/Kolkata",
                    "is_active": shift.is_active,
                    "priority": 50,
                    "effective_from": None,
                    "effective_to": None,
                    "notes": None
                })

            return {
                "success": True,
                "count": len(grouped_data),
                "grouped_shifts": list(grouped_data.values())
            }

        # Regular list
        return {
            "success": True,
            "count": len(shifts),
            "shifts": [
                {
                    "id": s.id,
                    "team_member_id": s.team_member_id,
                    "team_level": s.team_level,
                    "day_of_week": s.day_of_week,
                    "start_hour": s.start_hour,
                    "start_minute": 0,
                    "end_hour": s.end_hour,
                    "end_minute": 0,
                    "timezone": "Asia/Kolkata",
                    "is_active": s.is_active,
                    "priority": 50,
                    "effective_from": None,
                    "effective_to": None,
                    "notes": None
                }
                for s in shifts
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get shifts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/shifts", tags=["Shifts"])
async def create_shift_v1(
    user: User = Depends(require_admin),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Create new shift assignment - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, "POST /api/v1/shifts")
    try:
        shift = ShiftAssignment(
            team_member_id=payload.get("team_member_id"),
            team_level=payload.get("team_level"),
            day_of_week=payload.get("day_of_week"),
            start_hour=payload.get("start_hour", 9),
            end_hour=payload.get("end_hour", 17),
            is_active=payload.get("is_active", True)
        )
        db.add(shift)
        db.commit()
        db.refresh(shift)

        logger.info(f"✅ Created shift {shift.id} for member {shift.team_member_id}")

        return {
            "success": True,
            "shift": {
                "id": shift.id,
                "team_member_id": shift.team_member_id,
                "team_level": shift.team_level,
                "day_of_week": shift.day_of_week,
                "start_hour": shift.start_hour,
                "start_minute": 0,
                "end_hour": shift.end_hour,
                "end_minute": 0,
                "timezone": "Asia/Kolkata",
                "is_active": shift.is_active,
                "priority": 50
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create shift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/shifts/{shift_id}", tags=["Shifts"])
async def update_shift_v1(
    shift_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Update existing shift - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"PUT /api/v1/shifts/{shift_id}")
    try:
        shift = db.query(ShiftAssignment).filter(ShiftAssignment.id == shift_id).first()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")

        # Update fields
        if "team_member_id" in payload:
            shift.team_member_id = payload["team_member_id"]
        if "team_level" in payload:
            shift.team_level = payload["team_level"]
        if "day_of_week" in payload:
            shift.day_of_week = payload["day_of_week"]
        if "start_hour" in payload:
            shift.start_hour = payload["start_hour"]
        if "end_hour" in payload:
            shift.end_hour = payload["end_hour"]
        if "is_active" in payload:
            shift.is_active = payload["is_active"]

        db.commit()
        db.refresh(shift)

        logger.info(f"✅ Updated shift {shift_id}")

        return {
            "success": True,
            "shift": {
                "id": shift.id,
                "team_member_id": shift.team_member_id,
                "team_level": shift.team_level,
                "day_of_week": shift.day_of_week,
                "start_hour": shift.start_hour,
                "start_minute": 0,
                "end_hour": shift.end_hour,
                "end_minute": 0,
                "is_active": shift.is_active
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update shift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/shifts/{shift_id}", tags=["Shifts"])
async def delete_shift_v1(
    shift_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Delete shift assignment - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"DELETE /api/v1/shifts/{shift_id}")
    try:
        shift = db.query(ShiftAssignment).filter(ShiftAssignment.id == shift_id).first()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")

        db.delete(shift)
        db.commit()

        logger.info(f"✅ Deleted shift {shift_id}")

        return {"success": True, "message": "Shift deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete shift: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LEAVES ENDPOINTS
# ============================================================================

@app.get("/api/v1/leaves", tags=["Leaves"])
async def get_leaves_v1(
    user: User = Depends(require_manager),
    request: Request = None,
    team_level: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    include_past: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Get all leave requests - Requires: Manager, Admin, or Super Admin role"""
    log_request(logger, request, user.id, "GET /api/v1/leaves")
    try:
        from sqlalchemy import Table, MetaData

        query = db.query(MemberLeave)

        if team_level:
            metadata = MetaData()
            team_members = Table('team_members', metadata, autoload_with=engine)
            member_ids = [r.id for r in db.execute(
                team_members.select().where(team_members.c.team_level == team_level)
            ).fetchall()]
            query = query.filter(MemberLeave.team_member_id.in_(member_ids))

        if status:
            query = query.filter(MemberLeave.status == status)

        if not include_past:
            today = date.today()
            query = query.filter(MemberLeave.end_date >= today)

        leaves = query.order_by(MemberLeave.created_at.desc()).all()

        # Enrich with member info
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        result = []
        for leave in leaves:
            member_result = db.execute(
                team_members.select().where(team_members.c.id == leave.team_member_id)
            ).first()

            result.append({
                "id": leave.id,
                "team_member_id": leave.team_member_id,
                "team_member_name": member_result.name if member_result else f"Member {leave.team_member_id}",
                "team_level": member_result.team_level if member_result else None,
                "start_date": leave.start_date.isoformat() if leave.start_date else None,
                "end_date": leave.end_date.isoformat() if leave.end_date else None,
                "leave_type": leave.leave_type,
                "status": leave.status,
                "reason": leave.reason,
                "created_at": leave.created_at.isoformat() if leave.created_at else None
            })

        return {
            "success": True,
            "count": len(result),
            "leaves": result
        }
    except Exception as e:
        logger.error(f"Failed to get leaves: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/leaves/me", tags=["Leaves"])
async def get_my_leaves_v1(
    user: User = Depends(get_current_user),
    request: Request = None,
    include_past: bool = Query(True),
    db: Session = Depends(get_db)
):
    """Get my leave requests - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/leaves/me")
    try:
        # In microservices, we don't have current_user context
        # This endpoint returns all leaves for now
        # Frontend should filter by user's team_member_id
        query = db.query(MemberLeave)

        if not include_past:
            today = date.today()
            query = query.filter(MemberLeave.end_date >= today)

        leaves = query.order_by(MemberLeave.created_at.desc()).all()

        result = []
        for leave in leaves:
            result.append({
                "id": leave.id,
                "team_member_id": leave.team_member_id,
                "start_date": leave.start_date.isoformat() if leave.start_date else None,
                "end_date": leave.end_date.isoformat() if leave.end_date else None,
                "leave_type": leave.leave_type,
                "status": leave.status,
                "reason": leave.reason
            })

        return {
            "success": True,
            "count": len(result),
            "leaves": result
        }
    except Exception as e:
        logger.error(f"Failed to get my leaves: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/leaves", tags=["Leaves"])
async def create_leave_v1(
    user: User = Depends(get_current_user),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Create leave request - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "POST /api/v1/leaves")
    try:
        leave = MemberLeave(
            team_member_id=payload.get("team_member_id"),
            start_date=datetime.fromisoformat(payload["start_date"]).date(),
            end_date=datetime.fromisoformat(payload["end_date"]).date(),
            leave_type=payload.get("leave_type", "vacation"),
            status="pending",  # Default to pending
            reason=payload.get("reason", "")
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)

        logger.info(f"✅ Created leave request {leave.id}")

        return {
            "success": True,
            "leave": {
                "id": leave.id,
                "team_member_id": leave.team_member_id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "leave_type": leave.leave_type,
                "status": leave.status,
                "reason": leave.reason
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create leave: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/leaves/{leave_id}", tags=["Leaves"])
async def update_leave_v1(
    leave_id: int,
    user: User = Depends(get_current_user),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Update leave request - Requires: Any authenticated user (with ownership check)"""
    log_request(logger, request, user.id, f"PUT /api/v1/leaves/{leave_id}")
    try:
        leave = db.query(MemberLeave).filter(MemberLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave not found")

        if "start_date" in payload:
            leave.start_date = datetime.fromisoformat(payload["start_date"]).date()
        if "end_date" in payload:
            leave.end_date = datetime.fromisoformat(payload["end_date"]).date()
        if "leave_type" in payload:
            leave.leave_type = payload["leave_type"]
        if "reason" in payload:
            leave.reason = payload["reason"]
        if "status" in payload:
            leave.status = payload["status"]

        db.commit()
        db.refresh(leave)

        logger.info(f"✅ Updated leave {leave_id}")

        return {
            "success": True,
            "leave": {
                "id": leave.id,
                "team_member_id": leave.team_member_id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "leave_type": leave.leave_type,
                "status": leave.status,
                "reason": leave.reason
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update leave: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/leaves/{leave_id}", tags=["Leaves"])
async def delete_leave_v1(
    leave_id: int,
    user: User = Depends(require_manager),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """Delete leave request - Requires: Manager, Admin, or Super Admin role"""
    log_request(logger, request, user.id, f"DELETE /api/v1/leaves/{leave_id}")
    try:
        leave = db.query(MemberLeave).filter(MemberLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave not found")

        db.delete(leave)
        db.commit()

        logger.info(f"✅ Deleted leave {leave_id}")

        return {"success": True, "message": "Leave deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete leave: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/leaves/{leave_id}/status", tags=["Leaves"])
async def update_leave_status_v1(
    leave_id: int,
    user: User = Depends(require_manager),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Update leave status (approve/reject) - Requires: Manager, Admin, or Super Admin role"""
    log_request(logger, request, user.id, f"POST /api/v1/leaves/{leave_id}/status")
    try:
        leave = db.query(MemberLeave).filter(MemberLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave not found")

        if "status" not in payload:
            raise HTTPException(status_code=400, detail="Status is required")

        leave.status = payload["status"]
        db.commit()
        db.refresh(leave)

        logger.info(f"✅ Updated leave {leave_id} status to {leave.status}")

        return {
            "success": True,
            "leave": {
                "id": leave.id,
                "team_member_id": leave.team_member_id,
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "leave_type": leave.leave_type,
                "status": leave.status,
                "reason": leave.reason
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update leave status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ON-CALL ENDPOINTS
# ============================================================================

@app.get("/api/v1/oncall/assignments", tags=["On-Call"])
async def get_oncall_assignments_v1(
    user: User = Depends(get_current_user),
    request: Request = None,
    week_start: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get on-call assignments for a week - Requires: Any authenticated user"""
    log_request(logger, request, user.id, "GET /api/v1/oncall/assignments")
    try:
        from sqlalchemy import Table, MetaData, and_

        if week_start:
            week_start_date = datetime.fromisoformat(week_start).date()
        else:
            # Get current week Monday
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())

        assignments = db.query(OnCallAssignment).filter(
            and_(
                OnCallAssignment.week_start == week_start_date,
                OnCallAssignment.is_active == True
            )
        ).all()

        # Enrich with member info
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        result = []
        for assignment in assignments:
            member_result = None
            if assignment.team_member_id:
                member_result = db.execute(
                    team_members.select().where(team_members.c.id == assignment.team_member_id)
                ).first()

            result.append({
                "id": assignment.id,
                "team_level": assignment.team_level,
                "team_member_id": assignment.team_member_id,
                "team_member_name": member_result.name if member_result else "Unassigned",
                "week_start": assignment.week_start.isoformat(),
                "week_end": assignment.week_end.isoformat(),
                "status": "active" if assignment.is_active else "inactive"
            })

        return {
            "success": True,
            "count": len(result),
            "assignments": result
        }
    except Exception as e:
        logger.error(f"Failed to get on-call assignments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/oncall/assignments/run", tags=["On-Call"])
async def run_oncall_assignments_v1(
    user: User = Depends(require_manager),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Generate on-call roster for a week - Requires: Manager, Admin, or Super Admin role"""
    log_request(logger, request, user.id, "POST /api/v1/oncall/assignments/run")
    try:
        from sqlalchemy import Table, MetaData, and_

        week_start_str = payload.get("week_start")
        force = payload.get("force", False)

        if week_start_str:
            week_start_date = datetime.fromisoformat(week_start_str).date()
        else:
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())

        week_end_date = week_start_date + timedelta(days=6)

        # Check if already exists
        existing = db.query(OnCallAssignment).filter(
            and_(
                OnCallAssignment.week_start == week_start_date,
                OnCallAssignment.is_active == True
            )
        ).first()

        if existing and not force:
            raise HTTPException(
                status_code=400,
                detail=f"On-call roster already exists for week {week_start_date}. Use force=true to regenerate."
            )

        # Deactivate existing if force
        if force and existing:
            db.query(OnCallAssignment).filter(
                OnCallAssignment.week_start == week_start_date
            ).update({"is_active": False})

        # Create new assignments for L2 and L3
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        created = []
        for level in ['L2', 'L3']:
            members = db.execute(
                team_members.select().where(
                    and_(
                        team_members.c.active == True,
                        team_members.c.team_level == level
                    )
                )
            ).fetchall()

            if members:
                # Simple: pick first available
                member = members[0]
                assignment = OnCallAssignment(
                    team_member_id=member.id,
                    team_level=level,
                    week_start=week_start_date,
                    week_end=week_end_date,
                    is_active=True
                )
                db.add(assignment)
                created.append({
                    "team_level": level,
                    "team_member_name": member.name
                })

        db.commit()

        logger.info(f"✅ Created on-call roster for week {week_start_date}")

        # Return all assignments
        assignments = db.query(OnCallAssignment).filter(
            and_(
                OnCallAssignment.week_start == week_start_date,
                OnCallAssignment.is_active == True
            )
        ).all()

        result = []
        for assignment in assignments:
            member_result = None
            if assignment.team_member_id:
                member_result = db.execute(
                    team_members.select().where(team_members.c.id == assignment.team_member_id)
                ).first()

            result.append({
                "id": assignment.id,
                "team_level": assignment.team_level,
                "team_member_id": assignment.team_member_id,
                "team_member_name": member_result.name if member_result else "Unassigned",
                "week_start": assignment.week_start.isoformat(),
                "week_end": assignment.week_end.isoformat(),
                "status": "active"
            })

        return {
            "success": True,
            "count": len(result),
            "assignments": result
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to run on-call assignments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/oncall/rotate", tags=["On-Call"])
async def rotate_oncall_v1(
    user: User = Depends(require_manager),
    request: Request = None,
    team_level: str = Query(...),
    week_start: str = Query(...),
    db: Session = Depends(get_db)
):
    """Rotate on-call assignment to next member - Requires: Manager, Admin, or Super Admin role"""
    log_request(logger, request, user.id, "GET /api/v1/oncall/rotate")
    try:
        from sqlalchemy import Table, MetaData, and_

        week_start_date = datetime.fromisoformat(week_start).date()

        # Find current assignment
        assignment = db.query(OnCallAssignment).filter(
            and_(
                OnCallAssignment.week_start == week_start_date,
                OnCallAssignment.team_level == team_level,
                OnCallAssignment.is_active == True
            )
        ).first()

        if not assignment:
            raise HTTPException(status_code=404, detail="On-call assignment not found")

        # Get next member
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)

        members = db.execute(
            team_members.select().where(
                and_(
                    team_members.c.active == True,
                    team_members.c.team_level == team_level
                )
            )
        ).fetchall()

        if not members:
            raise HTTPException(status_code=400, detail="No available members for rotation")

        # Find next member (simple round-robin)
        current_idx = next((i for i, m in enumerate(members) if m.id == assignment.team_member_id), -1)
        next_idx = (current_idx + 1) % len(members)
        next_member = members[next_idx]

        # Update assignment
        assignment.team_member_id = next_member.id
        db.commit()

        logger.info(f"✅ Rotated {team_level} on-call to {next_member.name}")

        return {
            "success": True,
            "assignment": {
                "id": assignment.id,
                "team_level": assignment.team_level,
                "team_member_id": assignment.team_member_id,
                "team_member_name": next_member.name,
                "week_start": assignment.week_start.isoformat(),
                "week_end": assignment.week_end.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to rotate on-call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/oncall/assignments/{assignment_id}/replace", tags=["On-Call"])
async def replace_oncall_assignment_v1(
    assignment_id: int,
    user: User = Depends(require_admin),
    request: Request = None,
    payload: dict = None,
    db: Session = Depends(get_db)
):
    """Replace engineer in on-call assignment - Requires: Admin or Super Admin role"""
    log_request(logger, request, user.id, f"POST /api/v1/oncall/assignments/{assignment_id}/replace")
    try:
        from sqlalchemy import Table, MetaData

        assignment = db.query(OnCallAssignment).filter(
            OnCallAssignment.id == assignment_id
        ).first()

        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        new_member_id = payload.get("team_member_id")
        if not new_member_id:
            raise HTTPException(status_code=400, detail="team_member_id is required")

        # Verify member exists
        metadata = MetaData()
        team_members = Table('team_members', metadata, autoload_with=engine)
        member_result = db.execute(
            team_members.select().where(team_members.c.id == new_member_id)
        ).first()

        if not member_result:
            raise HTTPException(status_code=404, detail="Team member not found")

        # Update assignment
        assignment.team_member_id = new_member_id
        db.commit()

        logger.info(f"✅ Replaced on-call assignment {assignment_id} with member {new_member_id}")

        return {
            "success": True,
            "assignment": {
                "id": assignment.id,
                "team_level": assignment.team_level,
                "team_member_id": assignment.team_member_id,
                "team_member_name": member_result.name,
                "week_start": assignment.week_start.isoformat(),
                "week_end": assignment.week_end.isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to replace on-call assignment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.SERVICE_PORT, reload=True)
