#!/usr/bin/env python3
"""
SLA Management Service - Enterprise-grade SLA tracking and alerting
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from loguru import logger

from app.models.sla import SLAPolicy, SLATracker, SLABreach, SLAStatus
from app.models.ticket import TicketHistory
from app.core.database import get_redis


class SLAManager:
    """Manages SLA lifecycle for tickets"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
        # Default SLA configuration used as a safety net when explicit policies
        # have not yet been configured in the database.
        self._default_policies = {
            "P1(Critical)": dict(response=15, resolution=240, escalation=120),
            "P2(High)": dict(response=60, resolution=480, escalation=240),
            "P3(Medium)": dict(response=120, resolution=720, escalation=360),
            "P4(Low)": dict(response=240, resolution=1440, escalation=720),
            "P5(Trivial)": dict(response=480, resolution=2880, escalation=1440),
        }

    def get_policy(self, priority: str, environment: str = None) -> Optional[SLAPolicy]:
        """Get SLA policy for given priority and environment"""
        query = self.db.query(SLAPolicy).filter(
            SLAPolicy.priority == priority,
            SLAPolicy.active == True
        )

        # Try environment-specific first
        if environment:
            policy = query.filter(SLAPolicy.environment == environment).first()
            if policy:
                return policy

        # Fallback to general policy (environment agnostic)
        policy = query.filter(SLAPolicy.environment == None).first()
        if policy:
            return policy

        # As a final fallback, create a default policy on the fly so that SLA
        # tracking can proceed without failing the pipeline.
        defaults = self._default_policies.get(priority)
        if not defaults:
            logger.error(f"No SLA defaults defined for priority {priority}")
            return None

        policy = SLAPolicy(
            priority=priority,
            response_time_minutes=defaults["response"],
            resolution_time_minutes=defaults["resolution"],
            escalation_time_minutes=defaults["escalation"],
            environment=None,
            business_hours_only=True,
            active=True,
            created_by="system_auto"
        )
        self.db.add(policy)
        self.db.commit()
        self.db.refresh(policy)
        logger.warning(
            f"Created default SLA policy for {priority}/ALL environments "
            "because none was configured."
        )
        return policy

    def start_sla_tracking(
        self,
        ticket_id: int,
        priority: str,
        environment: str = None
    ) -> Optional[SLATracker]:
        """Start SLA tracking when ticket is assigned"""
        try:
            # Get ticket
            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return None

            # Check if already tracking
            existing = self.db.query(SLATracker).filter(
                SLATracker.ticket_id == ticket_id
            ).first()

            if existing:
                logger.warning(f"SLA already tracking for ticket {ticket_id}")
                return existing

            # Get policy
            policy = self.get_policy(priority, environment)
            if not policy:
                logger.error(f"No SLA policy found for {priority}/{environment}")
                return None

            # Calculate deadlines
            now = datetime.now(timezone.utc)
            response_deadline = now + timedelta(minutes=policy.response_time_minutes)
            resolution_deadline = now + timedelta(minutes=policy.resolution_time_minutes)
            escalation_deadline = now + timedelta(minutes=policy.escalation_time_minutes)

            # Create tracker
            tracker = SLATracker(
                ticket_id=ticket_id,
                policy_id=policy.id,
                status=SLAStatus.WITHIN_SLA,
                response_deadline=response_deadline,
                resolution_deadline=resolution_deadline,
                escalation_deadline=escalation_deadline,
            )

            self.db.add(tracker)

            # Update ticket with SLA deadline
            ticket.sla_deadline = resolution_deadline

            self.db.commit()
            self.db.refresh(tracker)

            # Cache in Redis for fast lookup
            self._cache_sla_tracker(tracker)

            logger.info(
                f"✅ SLA tracking started for ticket {ticket_id}: "
                f"Resolution deadline in {policy.resolution_time_minutes}min"
            )

            return tracker

        except Exception as e:
            logger.error(f"❌ Error starting SLA tracking for ticket {ticket_id}: {e}")
            self.db.rollback()
            return None

    def update_sla_status(self, ticket_id: int) -> Optional[SLATracker]:
        """Update SLA status based on current time"""
        try:
            tracker = self.db.query(SLATracker).filter(
                SLATracker.ticket_id == ticket_id
            ).first()

            if not tracker:
                return None

            if tracker.paused:
                logger.debug(f"SLA paused for ticket {ticket_id}")
                return tracker

            now = datetime.now(timezone.utc)

            # Check response SLA
            if not tracker.actual_response_time:
                if now > tracker.response_deadline:
                    tracker.response_breached = True
                    tracker.response_breach_minutes = int(
                        (now - tracker.response_deadline).total_seconds() / 60
                    )

            # Check resolution SLA
            if now > tracker.resolution_deadline:
                tracker.resolution_breached = True
                tracker.resolution_breach_minutes = int(
                    (now - tracker.resolution_deadline).total_seconds() / 60
                )
                tracker.status = SLAStatus.BREACHED

                # Record breach
                if not tracker.breach_alert_sent:
                    self._record_sla_breach(tracker)
                    tracker.breach_alert_sent = True

            else:
                # Calculate completion percentage
                completion = tracker.get_completion_percentage("resolution")

                if completion >= 90:
                    tracker.status = SLAStatus.CRITICAL
                    if not tracker.critical_alert_sent:
                        self._send_critical_alert(tracker)
                        tracker.critical_alert_sent = True

                elif completion >= 80:
                    tracker.status = SLAStatus.AT_RISK
                    if not tracker.warning_alert_sent:
                        self._send_warning_alert(tracker)
                        tracker.warning_alert_sent = True

            # AUTO-ESCALATION DISABLED - Users escalate manually from UI
            # Auto-escalation is now handled by users through the UI
            # if not tracker.escalation_triggered and now > tracker.escalation_deadline:
            #     tracker.escalation_triggered = True
            #     self._trigger_auto_escalation(tracker)

            self.db.commit()
            self.db.refresh(tracker)

            # Update cache
            self._cache_sla_tracker(tracker)

            return tracker

        except Exception as e:
            logger.error(f"❌ Error updating SLA status for ticket {ticket_id}: {e}")
            self.db.rollback()
            return None

    def mark_response_completed(self, ticket_id: int):
        """Mark first response as completed"""
        tracker = self.db.query(SLATracker).filter(
            SLATracker.ticket_id == ticket_id
        ).first()

        if tracker and not tracker.actual_response_time:
            tracker.actual_response_time = datetime.now(timezone.utc)
            self.db.commit()
            logger.info(f"✅ First response completed for ticket {ticket_id}")

    def mark_resolution_completed(self, ticket_id: int):
        """Mark resolution as completed"""
        tracker = self.db.query(SLATracker).filter(
            SLATracker.ticket_id == ticket_id
        ).first()

        if tracker:
            tracker.actual_resolution_time = datetime.now(timezone.utc)
            if not tracker.resolution_breached:
                tracker.status = SLAStatus.WITHIN_SLA
            self.db.commit()
            logger.info(f"✅ Resolution completed for ticket {ticket_id}")

    def pause_sla(self, ticket_id: int):
        """Pause SLA timer (e.g., waiting for customer response)"""
        tracker = self.db.query(SLATracker).filter(
            SLATracker.ticket_id == ticket_id
        ).first()

        if tracker and not tracker.paused:
            tracker.paused = True
            tracker.paused_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info(f"⏸️ SLA paused for ticket {ticket_id}")

    def resume_sla(self, ticket_id: int):
        """Resume SLA timer"""
        tracker = self.db.query(SLATracker).filter(
            SLATracker.ticket_id == ticket_id
        ).first()

        if tracker and tracker.paused:
            now = datetime.now(timezone.utc)
            paused_duration = int((now - tracker.paused_at).total_seconds() / 60)
            tracker.total_paused_minutes += paused_duration

            # Extend deadlines by paused duration
            extension = timedelta(minutes=paused_duration)
            tracker.response_deadline += extension
            tracker.resolution_deadline += extension
            tracker.escalation_deadline += extension

            tracker.paused = False
            tracker.paused_at = None

            self.db.commit()
            logger.info(f"▶️ SLA resumed for ticket {ticket_id} (extended by {paused_duration}min)")

    def get_sla_status(self, ticket_id: int) -> Dict:
        """Get current SLA status for a ticket"""
        # Try cache first
        cached = self.redis.get(f"sla:tracker:{ticket_id}")
        if cached:
            import json
            return json.loads(cached)

        tracker = self.db.query(SLATracker).filter(
            SLATracker.ticket_id == ticket_id
        ).first()

        if not tracker:
            return {"error": "No SLA tracking found"}

        response_remaining = tracker.calculate_time_remaining("response")
        resolution_remaining = tracker.calculate_time_remaining("resolution")
        completion = tracker.get_completion_percentage("resolution")

        status = {
            "status": tracker.status.value,
            "response_deadline": tracker.response_deadline.isoformat(),
            "resolution_deadline": tracker.resolution_deadline.isoformat(),
            "response_remaining_minutes": response_remaining,
            "resolution_remaining_minutes": resolution_remaining,
            "completion_percentage": round(completion, 2),
            "response_breached": tracker.response_breached,
            "resolution_breached": tracker.resolution_breached,
            "paused": tracker.paused,
        }

        return status

    def get_at_risk_tickets(self) -> List[Dict]:
        """Get all tickets at risk of SLA breach"""
        trackers = self.db.query(SLATracker).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL]),
            SLATracker.paused == False
        ).all()

        results = []
        for tracker in trackers:
            ticket = tracker.ticket
            results.append({
                "ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "priority": ticket.priority.value,
                "status": tracker.status.value,
                "remaining_minutes": tracker.calculate_time_remaining("resolution"),
                "assigned_to": ticket.assigned_to.name if ticket.assigned_to else None,
            })

        return results

    def _record_sla_breach(self, tracker: SLATracker):
        """Record SLA breach for reporting"""
        try:
            ticket = tracker.ticket

            breach = SLABreach(
                tracker_id=tracker.id,
                ticket_id=ticket.id,
                breach_type="resolution",
                breach_minutes=tracker.resolution_breach_minutes,
                priority=ticket.priority.value,
                environment=ticket.environment,
                assigned_to_id=ticket.assigned_to_id,
                team_level=ticket.team_level,
            )

            self.db.add(breach)

            # Update ticket
            ticket.sla_breached = True
            ticket.sla_breach_minutes = tracker.resolution_breach_minutes

            self.db.commit()

            logger.error(
                f"🚨 SLA BREACH: Ticket {ticket.redmine_ticket_id} breached by "
                f"{tracker.resolution_breach_minutes} minutes"
            )

        except Exception as e:
            logger.error(f"❌ Error recording SLA breach: {e}")
            self.db.rollback()

    def _send_warning_alert(self, tracker: SLATracker):
        """Send 80% warning alert"""
        from app.services.notification_service import NotificationService

        notification_service = NotificationService(self.db)
        notification_service.send_sla_warning_alert(tracker)

        logger.warning(f"⚠️ SLA warning sent for ticket {tracker.ticket.redmine_ticket_id}")

    def _send_critical_alert(self, tracker: SLATracker):
        """Send 90% critical alert"""
        from app.services.notification_service import NotificationService

        notification_service = NotificationService(self.db)
        notification_service.send_sla_critical_alert(tracker)

        logger.error(f"🔴 SLA critical alert sent for ticket {tracker.ticket.redmine_ticket_id}")

    def _trigger_auto_escalation(self, tracker: SLATracker):
        """
        [DEPRECATED] Trigger automatic escalation on SLA deadline

        AUTO-ESCALATION HAS BEEN DISABLED
        Escalation is now handled manually by users through the UI.
        This method is kept for reference but is no longer called.
        """
        from app.services.escalation_service import EscalationService

        escalation_service = EscalationService(self.db)
        escalation_service.auto_escalate(
            tracker.ticket.id,
            reason="sla_deadline"
        )

        logger.warning(f"⬆️ Auto-escalation triggered for ticket {tracker.ticket.redmine_ticket_id}")

    def _cache_sla_tracker(self, tracker: SLATracker):
        """Cache SLA tracker in Redis for fast access"""
        import json

        data = {
            "ticket_id": tracker.ticket_id,
            "status": tracker.status.value,
            "resolution_deadline": tracker.resolution_deadline.isoformat(),
        }

        self.redis.setex(
            f"sla:tracker:{tracker.ticket_id}",
            300,  # 5 minutes TTL
            json.dumps(data)
        )
