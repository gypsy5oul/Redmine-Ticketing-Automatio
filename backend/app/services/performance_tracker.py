#!/usr/bin/env python3
"""
Performance Tracking Service - Tracks team member performance metrics
"""

from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from loguru import logger

from app.models.performance import PerformanceMetric, TicketResolutionMetric
from app.models.ticket import TicketHistory
from app.models.team import TeamMember


class PerformanceTracker:
    """Tracks and updates team member performance metrics"""

    def __init__(self, db: Session):
        self.db = db

    def record_ticket_assignment(self, ticket: TicketHistory) -> None:
        """
        Record ticket assignment in performance metrics

        Args:
            ticket: Newly assigned ticket
        """
        try:
            if not ticket.assigned_to_id:
                return

            today = date.today()
            metric = self._get_or_create_metric(ticket.assigned_to_id, today)

            metric.tickets_assigned += 1
            self.db.commit()

            logger.debug(f"📊 Recorded ticket assignment for member {ticket.assigned_to_id}")

        except Exception as e:
            logger.error(f"❌ Failed to record ticket assignment: {e}")
            self.db.rollback()

    def record_ticket_resolution(self, ticket: TicketHistory) -> None:
        """
        Record ticket resolution in performance metrics

        Args:
            ticket: Resolved ticket
        """
        try:
            if not ticket.assigned_to_id:
                return

            today = date.today()
            metric = self._get_or_create_metric(ticket.assigned_to_id, today)

            metric.tickets_resolved += 1

            # Calculate resolution time
            if ticket.assigned_at and ticket.resolved_at:
                resolution_hours = (ticket.resolved_at - ticket.assigned_at).total_seconds() / 3600

                # Update average resolution time
                if metric.avg_resolution_time_hours:
                    # Running average
                    total_resolved = metric.tickets_resolved
                    metric.avg_resolution_time_hours = (
                        (metric.avg_resolution_time_hours * (total_resolved - 1) + resolution_hours) / total_resolved
                    )
                else:
                    metric.avg_resolution_time_hours = resolution_hours

                # Create detailed resolution metric
                self._create_resolution_metric(ticket, resolution_hours)

            # Update SLA metrics
            if ticket.sla_breached:
                metric.sla_breached_count += 1
            else:
                metric.sla_met_count += 1

            # Calculate SLA compliance rate
            total_sla_tickets = metric.sla_met_count + metric.sla_breached_count
            if total_sla_tickets > 0:
                metric.sla_compliance_rate = (metric.sla_met_count / total_sla_tickets) * 100

            self.db.commit()

            logger.debug(f"📊 Recorded ticket resolution for member {ticket.assigned_to_id}")

        except Exception as e:
            logger.error(f"❌ Failed to record ticket resolution: {e}")
            self.db.rollback()

    def record_ticket_escalation(
        self,
        from_user_id: Optional[int],
        to_user_id: int,
        ticket_date: date = None
    ) -> None:
        """
        Record ticket escalation in performance metrics

        Args:
            from_user_id: User who escalated from (lost ticket)
            to_user_id: User who received escalation (got ticket)
            ticket_date: Date to record metrics (defaults to today)
        """
        try:
            metric_date = ticket_date or date.today()

            # Update metrics for user who escalated FROM (lost the ticket)
            if from_user_id:
                from_metric = self._get_or_create_metric(from_user_id, metric_date)
                from_metric.tickets_escalated += 1
                logger.debug(f"📊 Recorded escalation from member {from_user_id}")

            # Update metrics for user who received escalation (got the ticket)
            to_metric = self._get_or_create_metric(to_user_id, metric_date)
            to_metric.tickets_assigned += 1
            logger.debug(f"📊 Recorded escalation to member {to_user_id}")

            self.db.commit()

        except Exception as e:
            logger.error(f"❌ Failed to record ticket escalation: {e}")
            self.db.rollback()

    def record_ticket_reopen(self, ticket: TicketHistory) -> None:
        """
        Record ticket reopen in performance metrics

        Args:
            ticket: Reopened ticket
        """
        try:
            if not ticket.assigned_to_id:
                return

            today = date.today()
            metric = self._get_or_create_metric(ticket.assigned_to_id, today)

            metric.tickets_reopened += 1

            # Update reopened rate
            if metric.tickets_resolved > 0:
                metric.reopened_rate = (metric.tickets_reopened / metric.tickets_resolved) * 100

            self.db.commit()

            logger.debug(f"📊 Recorded ticket reopen for member {ticket.assigned_to_id}")

        except Exception as e:
            logger.error(f"❌ Failed to record ticket reopen: {e}")
            self.db.rollback()

    def record_collaboration(self, ticket_id: int, member_id: int) -> None:
        """
        Record collaboration in performance metrics

        Args:
            ticket_id: Ticket ID
            member_id: Team member who collaborated
        """
        try:
            today = date.today()
            metric = self._get_or_create_metric(member_id, today)

            metric.collaborative_tickets_count += 1
            self.db.commit()

            logger.debug(f"📊 Recorded collaboration for member {member_id}")

        except Exception as e:
            logger.error(f"❌ Failed to record collaboration: {e}")
            self.db.rollback()

    def update_team_member_aggregates(self, member_id: int) -> None:
        """
        Update team member's aggregate statistics

        Args:
            member_id: Team member ID
        """
        try:
            member = self.db.query(TeamMember).filter(TeamMember.id == member_id).first()
            if not member:
                return

            # Get all-time statistics
            resolved_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == member_id,
                TicketHistory.status == TicketStatus.RESOLVED
            ).all()

            # Update total resolved
            member.total_tickets_resolved = len(resolved_tickets)

            # Calculate average resolution time
            if resolved_tickets:
                total_hours = 0
                valid_count = 0

                for ticket in resolved_tickets:
                    if ticket.assigned_at and ticket.resolved_at:
                        hours = (ticket.resolved_at - ticket.assigned_at).total_seconds() / 3600
                        total_hours += hours
                        valid_count += 1

                if valid_count > 0:
                    member.avg_resolution_time_hours = total_hours / valid_count

            # Calculate SLA compliance
            tickets_with_sla = [t for t in resolved_tickets if t.sla_breached is not None]
            if tickets_with_sla:
                sla_met = sum(1 for t in tickets_with_sla if not t.sla_breached)
                member.sla_compliance_rate = (sla_met / len(tickets_with_sla)) * 100

            self.db.commit()

            logger.debug(f"📊 Updated aggregates for member {member_id}")

        except Exception as e:
            logger.error(f"❌ Failed to update team member aggregates: {e}")
            self.db.rollback()

    def _get_or_create_metric(self, member_id: int, metric_date: date) -> PerformanceMetric:
        """
        Get existing metric or create new one for member and date

        Args:
            member_id: Team member ID
            metric_date: Date for the metric

        Returns:
            PerformanceMetric instance
        """
        metric = self.db.query(PerformanceMetric).filter(
            and_(
                PerformanceMetric.team_member_id == member_id,
                PerformanceMetric.date == metric_date
            )
        ).first()

        if not metric:
            metric = PerformanceMetric(
                team_member_id=member_id,
                date=metric_date,
                tickets_assigned=0,
                tickets_resolved=0,
                tickets_escalated=0,
                tickets_reopened=0,
                sla_met_count=0,
                sla_breached_count=0,
                collaborative_tickets_count=0
            )
            self.db.add(metric)
            logger.debug(f"📊 Created new metric for member {member_id} on {metric_date}")

        return metric

    def _create_resolution_metric(self, ticket: TicketHistory, resolution_hours: float) -> None:
        """
        Create detailed resolution metric for ticket

        Args:
            ticket: Resolved ticket
            resolution_hours: Resolution time in hours
        """
        try:
            # Check if already exists
            existing = self.db.query(TicketResolutionMetric).filter(
                TicketResolutionMetric.ticket_id == ticket.id
            ).first()

            if existing:
                logger.debug(f"Resolution metric already exists for ticket {ticket.id}")
                return

            resolution_metric = TicketResolutionMetric(
                ticket_id=ticket.id,
                resolution_time_hours=resolution_hours,
                number_of_escalations=ticket.escalation_count or 0,
                sla_met=not ticket.sla_breached,
                sla_buffer_minutes=ticket.sla_breach_minutes or 0,
                reopened=False,
                reopened_count=0,
                collaboration_required=ticket.collaboration_required or False,
                resolved_at=ticket.resolved_at or datetime.now(timezone.utc)
            )

            self.db.add(resolution_metric)
            logger.debug(f"📊 Created resolution metric for ticket {ticket.id}")

        except Exception as e:
            logger.error(f"❌ Failed to create resolution metric: {e}")
