#!/usr/bin/env python3
"""
Escalation Service - Multi-level L1→L2→L3 escalation logic
"""

from typing import Optional, Dict, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from loguru import logger

from app.models.escalation import Escalation, EscalationReason, EscalationType
from app.models.ticket import TicketHistory, TicketStatus, ComplexityLevel
from app.models.team import TeamMember, TeamLevel
from app.services.ml_service import MLPredictionService
from app.core.database import get_redis


class EscalationService:
    """Manages multi-level ticket escalation (L1 → L2 → L3)"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
        self.ml_service = MLPredictionService(db)

    def auto_escalate(
        self,
        ticket_id: int,
        reason: str = "sla_deadline"
    ) -> Optional[Escalation]:
        """
        [DEPRECATED] Automatic escalation triggered by SLA breach or other conditions

        AUTO-ESCALATION HAS BEEN DISABLED
        This method is no longer used. Escalation is now handled manually by users
        through the UI. Manual escalation should use the manual_escalate() method instead.

        Args:
            ticket_id: Ticket to escalate
            reason: sla_deadline, no_response, complexity, etc.

        Returns:
            Escalation record or None
        """
        try:
            normalized_reason = self._normalize_reason(reason)

            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                logger.error(f"Ticket {ticket_id} not found for escalation")
                return None

            # Determine next level
            current_level = ticket.team_level
            next_level = self._get_next_level(current_level)

            if not next_level:
                logger.warning(f"Cannot escalate ticket {ticket_id} - already at highest level (L3)")
                return self._notify_management(ticket)

            # Find best assignee at next level
            next_assignee = self._find_best_escalation_target(ticket, next_level)

            if not next_assignee:
                logger.error(f"No available {next_level} members for escalation")
                return None

            # Create escalation record
            escalation = Escalation(
                ticket_id=ticket.id,
                from_user_id=ticket.assigned_to_id,
                to_user_id=next_assignee.id,
                from_team_level=current_level,
                to_team_level=next_level,
                reason=normalized_reason,
                escalation_type=EscalationType.AUTO,
                description=self._generate_escalation_description(ticket, normalized_reason),
                priority_at_escalation=ticket.priority.value,
                sla_status_at_escalation=self._get_sla_status(ticket.id),
                escalated_by="System",
            )

            self.db.add(escalation)

            # Update ticket
            old_assignee_id = ticket.assigned_to_id
            ticket.assigned_to_id = next_assignee.id
            ticket.team_level = next_level
            ticket.escalation_count += 1
            ticket.escalated = True

            self.db.commit()
            self.db.refresh(escalation)

            # Record performance metrics for escalation
            try:
                from app.services.performance_tracker import PerformanceTracker
                performance_tracker = PerformanceTracker(self.db)
                performance_tracker.record_ticket_escalation(
                    from_user_id=old_assignee_id,
                    to_user_id=next_assignee.id
                )
            except Exception as perf_error:
                logger.warning(f"⚠️ Failed to record escalation performance metric: {perf_error}")

            logger.info(
                f"✅ Auto-escalated ticket #{ticket.redmine_ticket_id}: "
                f"{current_level} → {next_level} (Reason: {reason})"
            )

            # Update in Redmine
            self._update_redmine_escalation(ticket, escalation, next_assignee)

            # Send notifications
            self._send_escalation_notifications(ticket, escalation, next_assignee)

            # Cache escalation
            self._cache_escalation(ticket.id, escalation)

            return escalation

        except Exception as e:
            logger.error(f"❌ Auto-escalation failed for ticket {ticket_id}: {e}")
            self.db.rollback()
            return None

    def manual_escalate(
        self,
        ticket_id: int,
        to_level: str,
        reason: str,
        description: str,
        escalated_by: str
    ) -> Optional[Escalation]:
        """
        Manual escalation triggered by user

        Args:
            ticket_id: Ticket to escalate
            to_level: Target level (L2 or L3)
            reason: Reason for escalation
            description: Detailed explanation
            escalated_by: User who requested escalation

        Returns:
            Escalation record or None
        """
        try:
            normalized_reason = self._normalize_reason(reason)

            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return None

            # Validate escalation path
            if not self._is_valid_escalation_path(ticket.team_level, to_level):
                logger.error(f"Invalid escalation path: {ticket.team_level} → {to_level}")
                return None

            # Find best assignee
            next_assignee = self._find_best_escalation_target(ticket, to_level)

            if not next_assignee:
                logger.error(f"No available {to_level} members")
                return None

            # Create escalation
            escalation = Escalation(
                ticket_id=ticket.id,
                from_user_id=ticket.assigned_to_id,
                to_user_id=next_assignee.id,
                from_team_level=ticket.team_level,
                to_team_level=to_level,
                reason=normalized_reason,
                escalation_type=EscalationType.MANUAL,
                description=description or self._generate_escalation_description(ticket, normalized_reason),
                priority_at_escalation=ticket.priority.value,
                escalated_by=escalated_by,
            )

            self.db.add(escalation)

            # Update ticket
            old_level = ticket.team_level
            old_assignee_id = ticket.assigned_to_id
            ticket.assigned_to_id = next_assignee.id
            ticket.team_level = to_level
            ticket.escalation_count += 1
            ticket.escalated = True

            self.db.commit()
            self.db.refresh(escalation)

            # Record performance metrics for manual escalation
            try:
                from app.services.performance_tracker import PerformanceTracker
                performance_tracker = PerformanceTracker(self.db)
                performance_tracker.record_ticket_escalation(
                    from_user_id=old_assignee_id,
                    to_user_id=next_assignee.id
                )
            except Exception as perf_error:
                logger.warning(f"⚠️ Failed to record escalation performance metric: {perf_error}")

            logger.info(
                f"✅ Manual escalation: Ticket #{ticket.redmine_ticket_id} "
                f"{old_level} → {to_level} by {escalated_by}"
            )

            # Update Redmine
            self._update_redmine_escalation(ticket, escalation, next_assignee)

            # Send notifications
            self._send_escalation_notifications(ticket, escalation, next_assignee)

            return escalation

        except Exception as e:
            logger.error(f"❌ Manual escalation failed: {e}")
            self.db.rollback()
            return None

    def check_escalation_needed(self, ticket_id: int) -> Dict:
        """
        Check if ticket needs escalation based on various factors

        Returns:
            {
                "escalation_recommended": bool,
                "reasons": [],
                "confidence": 0.0-1.0,
                "recommended_level": "L2|L3"
            }
        """
        try:
            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket or not ticket.assigned_to:
                return {"escalation_recommended": False, "reasons": []}

            reasons = []
            confidence = 0.0

            # Check SLA breach
            if ticket.sla_breached:
                reasons.append("SLA breached")
                confidence += 0.4

            # Check time elapsed
            if ticket.assigned_at:
                hours_elapsed = (datetime.now(timezone.utc) - ticket.assigned_at).total_seconds() / 3600
                if hours_elapsed > 24:
                    reasons.append(f"Open for {int(hours_elapsed)} hours")
                    confidence += 0.2

            # Check assignee workload
            assignee_workload = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == ticket.assigned_to_id,
                TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
            ).count()

            if assignee_workload >= ticket.assigned_to.max_tickets:
                reasons.append("Assignee at capacity")
                confidence += 0.2

            # Check complexity (Enum-safe comparison)
            if ticket.complexity in {ComplexityLevel.COMPLEX, ComplexityLevel.CRITICAL}:
                reasons.append(f"High complexity ({ticket.complexity})")
                confidence += 0.2

            # Determine if escalation needed
            escalation_recommended = confidence >= 0.5

            # Recommend level
            current_level = ticket.team_level
            recommended_level = self._get_next_level(current_level) if escalation_recommended else current_level

            return {
                "escalation_recommended": escalation_recommended,
                "reasons": reasons,
                "confidence": min(confidence, 1.0),
                "recommended_level": recommended_level,
                "current_level": current_level
            }

        except Exception as e:
            logger.error(f"❌ Escalation check failed: {e}")
            return {"escalation_recommended": False, "reasons": ["Error checking"]}

    def get_escalation_history(self, ticket_id: int) -> List[Escalation]:
        """Get complete escalation history for a ticket"""
        return self.db.query(Escalation).filter(
            Escalation.ticket_id == ticket_id
        ).order_by(Escalation.escalated_at.desc()).all()

    def _get_next_level(self, current_level: str) -> Optional[str]:
        """Determine next escalation level"""
        level_progression = {
            "L1": "L2",
            "L2": "L3",
            "L3": None  # Already at highest
        }
        return level_progression.get(current_level)

    def _is_valid_escalation_path(self, from_level: str, to_level: str) -> bool:
        """Validate escalation path"""
        valid_paths = {
            "L1": ["L2", "L3"],
            "L2": ["L3"],
            "L3": []
        }
        return to_level in valid_paths.get(from_level, [])

    def _find_best_escalation_target(
        self,
        ticket: TicketHistory,
        target_level: str
    ) -> Optional[TeamMember]:
        """Find best team member at target level using ML service"""
        available_members: List[TeamMember] = []
        try:
            # Get available members at target level
            available_members = self.db.query(TeamMember).filter(
                TeamMember.team_level == TeamLevel(target_level),
                TeamMember.active == True
            ).all()

            if not available_members:
                return None

            # Use ML service for smart routing
            if ticket.category:
                best_assignee, confidence, reasons = self.ml_service.smart_route_ticket(
                    {"subject": ticket.subject, "environment": ticket.environment},
                    available_members,
                    ticket.category.value
                )
                logger.info(f"ML routing: {best_assignee.name} (confidence: {confidence:.2f})")
                return best_assignee
            else:
                # Fallback: member with lowest workload
                workloads = {}
                for member in available_members:
                    count = self.db.query(TicketHistory).filter(
                        TicketHistory.assigned_to_id == member.id,
                        TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
                    ).count()
                    workloads[member.id] = count

                return min(available_members, key=lambda m: workloads.get(m.id, 0))

        except Exception as e:
            logger.error(f"❌ Error finding escalation target: {e}")
            return available_members[0] if available_members else None

    def _generate_escalation_description(self, ticket: TicketHistory, reason: EscalationReason) -> str:
        """Generate escalation description"""
        descriptions = {
            EscalationReason.SLA_BREACH: f"Ticket escalated due to SLA breach. Priority: {ticket.priority.value}",
            EscalationReason.NO_RESPONSE: "Ticket escalated due to no response from assigned engineer.",
            EscalationReason.COMPLEXITY: f"Ticket escalated due to high complexity ({ticket.complexity}).",
            EscalationReason.MANUAL_REQUEST: "Ticket escalated upon manual request.",
            EscalationReason.SKILL_MISMATCH: "Ticket escalated due to skill mismatch.",
            EscalationReason.CAPACITY: "Ticket escalated due to capacity constraints.",
            EscalationReason.CUSTOMER_REQUEST: "Ticket escalated per customer request.",
            EscalationReason.REOPENED: "Ticket escalated after the issue was reopened.",
        }
        return descriptions.get(reason, f"Ticket escalated. Reason: {reason.value}")

    def _get_sla_status(self, ticket_id: int) -> str:
        """Get current SLA status"""
        try:
            from app.services.sla_manager import SLAManager
            sla_manager = SLAManager(self.db)
            status = sla_manager.get_sla_status(ticket_id)
            return status.get('status', 'unknown')
        except Exception:
            return 'unknown'

    def _update_redmine_escalation(
        self,
        ticket: TicketHistory,
        escalation: Escalation,
        new_assignee: TeamMember
    ):
        """Update Redmine with escalation info"""
        try:
            import requests
            from app.core.config import settings

            url = f"{settings.REDMINE_BASE_URL}/issues/{ticket.redmine_ticket_id}.json"

            escalation_note = f"""🔼 TICKET ESCALATED

Escalation Details:
• From: {escalation.from_team_level} → To: {escalation.to_team_level}
• Reason: {escalation.reason.value.replace('_', ' ').title()}
• New Assignee: {new_assignee.name}

{escalation.description}

This ticket has been escalated to our {escalation.to_team_level} support team for advanced troubleshooting and resolution.

---
Automated Escalation System
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            payload = {
                "issue": {
                    "assigned_to_id": new_assignee.redmine_user_id,
                    "notes": escalation_note
                }
            }

            response = requests.put(
                url,
                json=payload,
                headers={
                    'X-Redmine-API-Key': settings.REDMINE_API_KEY,
                    'Content-Type': 'application/json'
                },
                timeout=10
            )

            if response.status_code == 204:
                logger.info(f"✅ Redmine updated with escalation for ticket #{ticket.redmine_ticket_id}")
            else:
                logger.warning(f"⚠️ Redmine update failed: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Failed to update Redmine: {e}")

    def _send_escalation_notifications(
        self,
        ticket: TicketHistory,
        escalation: Escalation,
        new_assignee: TeamMember
    ):
        """Send escalation notifications"""
        try:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(self.db)
            notification_service.send_escalation_notification(ticket, escalation, new_assignee)
        except Exception as e:
            logger.error(f"❌ Failed to send escalation notification: {e}")

    def _notify_management(self, ticket: TicketHistory):
        """Notify management when L3 escalation fails"""
        logger.critical(
            f"🚨 CRITICAL: Ticket #{ticket.redmine_ticket_id} cannot be escalated "
            f"(already at L3). Management notification required."
        )
        # TODO: Send critical alert to management
        return None

    def _cache_escalation(self, ticket_id: int, escalation: Escalation):
        """Cache escalation in Redis"""
        try:
            import json
            data = {
                "ticket_id": ticket_id,
                "to_level": escalation.to_team_level,
                "reason": escalation.reason.value,
                "escalated_at": escalation.escalated_at.isoformat()
            }
            self.redis.setex(
                f"escalation:ticket:{ticket_id}",
                3600,  # 1 hour TTL
                json.dumps(data)
            )
        except Exception as e:
            logger.debug(f"Cache escalation failed: {e}")

    def _normalize_reason(self, reason: str) -> EscalationReason:
        """Map arbitrary reason strings to supported enumeration."""
        if not reason:
            return EscalationReason.MANUAL_REQUEST

        normalized = reason.lower()
        alias_map = {
            "sla_deadline": EscalationReason.SLA_BREACH,
            "deadline": EscalationReason.SLA_BREACH,
            "breach": EscalationReason.SLA_BREACH,
            "overdue": EscalationReason.SLA_BREACH,
        }

        mapped_reason = alias_map.get(normalized)
        if mapped_reason:
            return mapped_reason

        try:
            return EscalationReason(normalized)
        except ValueError:
            logger.warning(f"Unknown escalation reason '{reason}', defaulting to manual_request")
            return EscalationReason.MANUAL_REQUEST
