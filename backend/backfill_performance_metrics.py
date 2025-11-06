#!/usr/bin/env python3
"""
Backfill Performance Metrics Script
Generates performance metrics from historical ticket data
"""

import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

# Add app to path
sys.path.insert(0, '/app')

from app.core.config import settings
from app.models.ticket import TicketHistory
from app.models.team import TeamMember
from app.models.escalation import Escalation
from app.services.performance_tracker import PerformanceTracker


def backfill_performance_metrics():
    """Backfill performance metrics from historical data"""

    logger.info("=" * 80)
    logger.info("🔄 Starting Performance Metrics Backfill")
    logger.info("=" * 80)

    # Create database session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        performance_tracker = PerformanceTracker(db)

        # Get all tickets
        all_tickets = db.query(TicketHistory).all()
        logger.info(f"📊 Found {len(all_tickets)} tickets to process")

        # Process ticket assignments
        logger.info("📝 Processing ticket assignments...")
        assigned_count = 0
        for ticket in all_tickets:
            if ticket.assigned_to_id and ticket.assigned_at:
                try:
                    performance_tracker.record_ticket_assignment(ticket)
                    assigned_count += 1
                except Exception as e:
                    logger.debug(f"Skipped ticket {ticket.id}: {e}")

        logger.info(f"✅ Processed {assigned_count} ticket assignments")

        # Process ticket resolutions
        logger.info("📝 Processing ticket resolutions...")
        resolved_count = 0
        for ticket in all_tickets:
            if ticket.status == 'resolved' and ticket.resolved_at:
                try:
                    performance_tracker.record_ticket_resolution(ticket)
                    resolved_count += 1
                except Exception as e:
                    logger.debug(f"Skipped ticket {ticket.id}: {e}")

        logger.info(f"✅ Processed {resolved_count} ticket resolutions")

        # Process escalations
        logger.info("📝 Processing escalations...")
        escalations = db.query(Escalation).all()
        escalation_count = 0
        for escalation in escalations:
            try:
                performance_tracker.record_ticket_escalation(
                    from_user_id=escalation.from_user_id,
                    to_user_id=escalation.to_user_id,
                    ticket_date=escalation.escalated_at.date() if escalation.escalated_at else None
                )
                escalation_count += 1
            except Exception as e:
                logger.debug(f"Skipped escalation {escalation.id}: {e}")

        logger.info(f"✅ Processed {escalation_count} escalations")

        # Update team member aggregates
        logger.info("📝 Updating team member aggregates...")
        team_members = db.query(TeamMember).filter(TeamMember.active == True).all()
        for member in team_members:
            try:
                performance_tracker.update_team_member_aggregates(member.id)
            except Exception as e:
                logger.warning(f"Failed to update aggregates for {member.name}: {e}")

        logger.info(f"✅ Updated aggregates for {len(team_members)} team members")

        # Summary
        logger.info("=" * 80)
        logger.info("✅ BACKFILL COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 Ticket Assignments: {assigned_count}")
        logger.info(f"📊 Ticket Resolutions: {resolved_count}")
        logger.info(f"📊 Escalations: {escalation_count}")
        logger.info(f"📊 Team Members Updated: {len(team_members)}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        db.rollback()
        return False

    finally:
        db.close()

    return True


if __name__ == "__main__":
    success = backfill_performance_metrics()
    sys.exit(0 if success else 1)
