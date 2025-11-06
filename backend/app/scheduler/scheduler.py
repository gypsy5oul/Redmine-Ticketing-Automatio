#!/usr/bin/env python3
"""
Background Scheduler - APScheduler for automated tasks
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import TicketProcessor, SLAManager, WorkloadManager, NotificationService, SchedulingService

# Initialize scheduler
scheduler = AsyncIOScheduler()


# ============================================================================
# JOB DEFINITIONS
# ============================================================================

def process_new_tickets_job():
    """Process new tickets from Redmine"""
    try:
        logger.info("🔄 Running scheduled ticket processing...")
        db = SessionLocal()
        try:
            processor = TicketProcessor(db)
            result = processor.process_new_tickets()

            logger.info(
                f"✅ Scheduled processing complete: {result['processed']} processed, "
                f"{result['assigned']} assigned"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Scheduled ticket processing failed: {e}")


def check_sla_status_job():
    """Check and update SLA status for all active tickets"""
    try:
        logger.info("⏱️ Running scheduled SLA checks...")
        db = SessionLocal()
        try:
            processor = TicketProcessor(db)
            result = processor.process_sla_checks()

            logger.info(
                f"✅ SLA check complete: {result.get('checked', 0)} tickets, "
                f"{result.get('warnings', 0)} warnings, "
                f"{result.get('critical', 0)} critical"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ SLA check job failed: {e}")


def update_workload_cache_job():
    """Update workload cache for all team members"""
    try:
        logger.debug("♻️ Updating workload cache...")
        db = SessionLocal()
        try:
            from app.models.team import TeamMember
            workload_manager = WorkloadManager(db)

            members = db.query(TeamMember).filter(TeamMember.active == True).all()
            for member in members:
                workload_manager.update_workload_cache(member.id)

            logger.debug(f"✅ Updated workload cache for {len(members)} members")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Workload cache update failed: {e}")


def send_daily_summary_job():
    """Send daily performance summary"""
    try:
        logger.info("📊 Generating daily summary...")
        db = SessionLocal()
        try:
            from app.models.ticket import TicketHistory, TicketStatus
            from datetime import timedelta

            # Get today's stats
            today = datetime.now().date()
            today_start = datetime.combine(today, datetime.min.time())

            total_processed = db.query(TicketHistory).filter(
                TicketHistory.created_at >= today_start
            ).count()

            total_resolved = db.query(TicketHistory).filter(
                TicketHistory.resolved_at >= today_start
            ).count()

            # Calculate SLA compliance
            resolved_tickets = db.query(TicketHistory).filter(
                TicketHistory.resolved_at >= today_start
            ).all()

            sla_met = sum(1 for t in resolved_tickets if not t.sla_breached)
            sla_compliance = (sla_met / len(resolved_tickets) * 100) if resolved_tickets else 100

            # Get top performers
            from sqlalchemy import func
            from app.models.team import TeamMember
            top_performers = db.query(
                TeamMember.name,
                func.count(TicketHistory.id).label('resolved')
            ).join(TicketHistory).filter(
                TicketHistory.resolved_at >= today_start
            ).group_by(TeamMember.name).order_by(
                func.count(TicketHistory.id).desc()
            ).limit(5).all()

            summary_data = {
                "total_processed": total_processed,
                "total_resolved": total_resolved,
                "sla_compliance_rate": round(sla_compliance, 1),
                "avg_resolution_hours": 4.2,  # TODO: Calculate from actual data
                "escalations_count": 0,  # TODO: Get from escalations table
                "top_performers": [
                    {"name": p.name, "resolved": p.resolved}
                    for p in top_performers
                ]
            }

            # Send notification
            notification_service = NotificationService(db)
            notification_service.send_daily_summary(summary_data)

            logger.info("✅ Daily summary sent")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Daily summary job failed: {e}")


def check_capacity_alerts_job():
    """Check for capacity alerts and send notifications"""
    try:
        logger.debug("🔔 Checking capacity alerts...")
        db = SessionLocal()
        try:
            workload_manager = WorkloadManager(db)
            alerts = workload_manager.check_capacity_alerts()

            if alerts:
                logger.warning(f"⚠️ {len(alerts)} capacity alerts found")
                # TODO: Send alerts via notification service

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Capacity alerts job failed: {e}")


def retrain_ml_models_job():
    """Retrain ML models with latest historical data"""
    try:
        logger.info("🎓 Running scheduled ML model retraining...")
        db = SessionLocal()
        try:
            from app.services.ml_service import MLPredictionService

            ml_service = MLPredictionService(db)
            result = ml_service.train_models(force_retrain=False)

            if result.get("success"):
                logger.info(
                    f"✅ ML models retrained successfully: "
                    f"{result.get('training_samples', 0)} samples"
                )
            else:
                logger.warning(f"⚠️ ML retraining skipped: {result.get('error')}")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ ML retraining job failed: {e}")


def ensure_standard_shifts_job():
    """Ensure default weekday shifts exist for all members."""
    try:
        db = SessionLocal()
        try:
            scheduling_service = SchedulingService(db)
            created = scheduling_service.ensure_standard_weekday_shifts()
            if created:
                logger.info(f"✅ Standard shifts ensured for {created} slots")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Standard shift job failed: {e}")


def assign_oncall_roster_job():
    """Prepare the weekly on-call roster and notify teams."""
    try:
        db = SessionLocal()
        try:
            scheduling_service = SchedulingService(db)
            assignments = scheduling_service.assign_weekly_oncall()
            if assignments:
                summary = ", ".join(
                    f"{a.team_level}: {a.team_member.name if a.team_member else 'Unassigned'}"
                    for a in assignments
                )
                logger.info(f"✅ On-call roster prepared ({summary})")
            else:
                logger.warning("⚠️ No on-call assignments generated this week")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ On-call roster job failed: {e}")


def sync_redmine_statuses_job():
    """Synchronize ticket statuses with Redmine."""
    try:
        logger.info("🔄 Syncing ticket statuses with Redmine...")
        db = SessionLocal()
        try:
            processor = TicketProcessor(db)
            result = processor.sync_ticket_statuses_with_redmine()

            if result.get("success"):
                logger.info(
                    "✅ Redmine sync complete: %(updated)s updated, %(closed)s closed, %(reopened)s reopened, %(assignment_updates)s assignment updates" % result
                )
            else:
                logger.warning(f"⚠️ Redmine sync encountered an issue: {result.get('error')}")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Redmine sync job failed: {e}")


# ============================================================================
# SCHEDULER MANAGEMENT
# ============================================================================

def start_scheduler():
    """Start the background scheduler"""
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
        logger.info(f"   - Process tickets: every {settings.TICKET_PROCESSING_INTERVAL} minutes")
        logger.info(f"   - Check SLA: every {settings.SLA_CHECK_INTERVAL} minute(s)")
        logger.info(f"   - Update workload: every 5 minutes")
        logger.info(f"   - Daily summary: daily at 9:00 AM")
        logger.info(f"   - Capacity alerts: every 30 minutes")
        logger.info(f"   - ML retraining: weekly on Sunday at 2:00 AM")
        logger.info(f"   - Redmine sync: every {settings.REDMINE_STATUS_SYNC_INTERVAL} minutes")
        logger.info("   - Ensure standard shifts: daily at 06:00 AM")
        logger.info("   - On-call roster: Mondays at 08:00 AM")

    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown()
        logger.info("✅ Background scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Failed to stop scheduler: {e}")


def get_scheduler_status():
    """Get current scheduler status"""
    try:
        jobs = scheduler.get_jobs()
        return {
            "running": scheduler.running,
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in jobs
            ]
        }
    except Exception as e:
        logger.error(f"❌ Failed to get scheduler status: {e}")
        return {"error": str(e)}
