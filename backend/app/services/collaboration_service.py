#!/usr/bin/env python3
"""
Collaboration Service - Real-time multi-engineer collaboration
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from loguru import logger

from app.models.ticket import TicketHistory, TicketCollaboration
from app.models.team import TeamMember
from app.core.database import get_redis


class CollaborationService:
    """Manages multi-engineer collaboration on tickets"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()

    def add_collaborator(
        self,
        ticket_id: int,
        team_member_id: int,
        role: str = "secondary"
    ) -> Optional[TicketCollaboration]:
        """
        Add a collaborator to a ticket

        Args:
            ticket_id: Ticket ID
            team_member_id: Team member to add
            role: primary, secondary, consultant, observer

        Returns:
            TicketCollaboration record
        """
        try:
            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                logger.error(f"Ticket {ticket_id} not found")
                return None

            member = self.db.query(TeamMember).filter(
                TeamMember.id == team_member_id
            ).first()

            if not member:
                logger.error(f"Team member {team_member_id} not found")
                return None

            # Check if already collaborating
            existing = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.team_member_id == team_member_id,
                TicketCollaboration.is_active == True
            ).first()

            if existing:
                logger.warning(f"{member.name} already collaborating on ticket #{ticket.redmine_ticket_id}")
                return existing

            # Create collaboration record
            collaboration = TicketCollaboration(
                ticket_id=ticket_id,
                team_member_id=team_member_id,
                role=role,
                is_active=True
            )

            self.db.add(collaboration)

            # Update ticket flags
            ticket.is_collaborative = True
            ticket.collaborator_count = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.is_active == True
            ).count() + 1

            self.db.commit()
            self.db.refresh(collaboration)

            logger.info(f"✅ Added {member.name} as {role} to ticket #{ticket.redmine_ticket_id}")

            # Notify collaborators
            self._notify_collaboration_update(ticket, member, "joined")

            # Cache active collaborators
            self._cache_collaborators(ticket_id)

            return collaboration

        except Exception as e:
            logger.error(f"❌ Failed to add collaborator: {e}")
            self.db.rollback()
            return None

    def remove_collaborator(
        self,
        ticket_id: int,
        team_member_id: int
    ) -> bool:
        """Remove a collaborator from a ticket"""
        try:
            collaboration = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.team_member_id == team_member_id,
                TicketCollaboration.is_active == True
            ).first()

            if not collaboration:
                logger.warning(f"No active collaboration found")
                return False

            collaboration.is_active = False
            collaboration.left_at = datetime.now(timezone.utc)

            # Update ticket collaborator count
            ticket = collaboration.ticket
            ticket.collaborator_count = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.is_active == True
            ).count()

            if ticket.collaborator_count == 0:
                ticket.is_collaborative = False

            self.db.commit()

            logger.info(f"✅ Removed collaborator from ticket #{ticket.redmine_ticket_id}")

            # Notify
            self._notify_collaboration_update(ticket, collaboration.team_member, "left")

            # Update cache
            self._cache_collaborators(ticket_id)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to remove collaborator: {e}")
            self.db.rollback()
            return False

    def get_active_collaborators(self, ticket_id: int) -> List[Dict]:
        """Get all active collaborators for a ticket"""
        try:
            # Try cache first
            cached = self.redis.get(f"collaborators:ticket:{ticket_id}")
            if cached:
                import json
                return json.loads(cached)

            # Query database
            collaborations = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.is_active == True
            ).all()

            result = []
            for collab in collaborations:
                member = collab.team_member
                if not member:
                    continue

                team_level = (
                    member.team_level.value
                    if hasattr(member.team_level, "value")
                    else str(member.team_level) if member.team_level is not None
                    else None
                )

                result.append({
                    "id": collab.id,
                    "ticket_id": collab.ticket_id,
                    "team_member_id": collab.team_member_id,
                    "team_member": {
                        "id": member.id,
                        "name": member.name,
                        "email": member.email,
                        "team_level": team_level,
                    },
                    "role": collab.role,
                    "contribution_percentage": collab.contribution_percentage,
                    "joined_at": collab.joined_at.isoformat(),
                    "left_at": collab.left_at.isoformat() if collab.left_at else None,
                    "is_active": collab.is_active,
                    "comments_count": collab.comments_count,
                    "time_spent_hours": collab.time_spent_hours,
                })

            return result

        except Exception as e:
            logger.error(f"❌ Failed to get collaborators: {e}")
            return []

    def update_collaboration_metrics(
        self,
        ticket_id: int,
        team_member_id: int,
        comments_added: int = 0,
        time_spent_hours: float = 0.0
    ):
        """Update collaboration metrics (comments, time spent)"""
        try:
            collaboration = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.team_member_id == team_member_id,
                TicketCollaboration.is_active == True
            ).first()

            if not collaboration:
                return

            collaboration.comments_count += comments_added
            collaboration.time_spent_hours += time_spent_hours

            self.db.commit()

            logger.debug(
                f"Updated collaboration metrics: {collaboration.team_member.name} "
                f"on ticket #{collaboration.ticket.redmine_ticket_id}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to update collaboration metrics: {e}")
            self.db.rollback()

    def calculate_contribution_percentages(self, ticket_id: int):
        """Calculate contribution percentage for each collaborator"""
        try:
            collaborations = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id
            ).all()

            if not collaborations:
                return

            # Calculate total effort
            total_time = sum(c.time_spent_hours for c in collaborations)
            total_comments = sum(c.comments_count for c in collaborations)

            if total_time == 0 and total_comments == 0:
                return

            # Calculate percentages
            for collab in collaborations:
                time_weight = 0.7
                comment_weight = 0.3

                time_percentage = (
                    (collab.time_spent_hours / total_time * 100)
                    if total_time > 0 else 0
                )
                comment_percentage = (
                    (collab.comments_count / total_comments * 100)
                    if total_comments > 0 else 0
                )

                contribution = (
                    time_percentage * time_weight +
                    comment_percentage * comment_weight
                )

                collab.contribution_percentage = round(contribution, 1)

            self.db.commit()

            logger.info(f"✅ Calculated contributions for ticket #{ticket_id}")

        except Exception as e:
            logger.error(f"❌ Failed to calculate contributions: {e}")
            self.db.rollback()

    def get_collaboration_summary(self, ticket_id: int) -> Dict:
        """Get collaboration summary for a ticket"""
        try:
            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                return {}

            collaborators = self.get_active_collaborators(ticket_id)

            # Get past collaborators
            past_collaborators = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id,
                TicketCollaboration.is_active == False
            ).count()

            # Calculate total effort
            all_collabs = self.db.query(TicketCollaboration).filter(
                TicketCollaboration.ticket_id == ticket_id
            ).all()

            total_time = sum(c.time_spent_hours for c in all_collabs)
            total_comments = sum(c.comments_count for c in all_collabs)

            return {
                "ticket_id": ticket.redmine_ticket_id,
                "is_collaborative": ticket.is_collaborative,
                "active_collaborators": len(collaborators),
                "past_collaborators": past_collaborators,
                "total_collaborators": len(collaborators) + past_collaborators,
                "collaborators": collaborators,
                "total_time_spent_hours": round(total_time, 2),
                "total_comments": total_comments,
                "primary_assignee": {
                    "id": ticket.assigned_to.id,
                    "name": ticket.assigned_to.name
                } if ticket.assigned_to else None
            }

        except Exception as e:
            logger.error(f"❌ Failed to get collaboration summary: {e}")
            return {}

    def suggest_collaboration(self, ticket_id: int) -> List[Dict]:
        """
        Suggest additional collaborators based on ticket complexity

        Returns:
            List of suggested team members with reasons
        """
        try:
            ticket = self.db.query(TicketHistory).filter(
                TicketHistory.id == ticket_id
            ).first()

            if not ticket:
                return []

            suggestions = []

            # Suggest collaboration if:
            # 1. Complex ticket
            # 2. SLA at risk
            # 3. Multiple categories involved

            if ticket.complexity in ['complex', 'critical']:
                # Find members with relevant skills
                if ticket.category:
                    members = self.db.query(TeamMember).join(
                        TeamMember.skills
                    ).filter(
                        TeamMember.active == True,
                        TeamMember.id != ticket.assigned_to_id
                    ).all()

                    for member in members[:3]:  # Top 3 suggestions
                        suggestions.append({
                            "member_id": member.id,
                            "name": member.name,
                            "team_level": member.team_level,
                            "reason": f"Has expertise in {ticket.category.value}",
                            "confidence": 0.8
                        })

            return suggestions

        except Exception as e:
            logger.error(f"❌ Failed to suggest collaboration: {e}")
            return []

    def _notify_collaboration_update(
        self,
        ticket: TicketHistory,
        member: TeamMember,
        action: str
    ):
        """Send notification about collaboration update"""
        try:
            from app.services.notification_service import NotificationService
            notification_service = NotificationService(self.db)

            message = {
                "text": f"👥 Collaboration Update - Ticket #{ticket.redmine_ticket_id}",
                "cards": [{
                    "header": {
                        "title": f"👥 Collaboration Update",
                        "subtitle": f"{member.name} {action} the collaboration"
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "Ticket",
                                    "content": f"#{ticket.redmine_ticket_id}: {ticket.subject[:50]}"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Collaborator",
                                    "content": f"{member.name} ({member.team_level})"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Action",
                                    "content": action.title()
                                }
                            }
                        ]
                    }]
                }]
            }

            notification_service._send_google_chat(message)

        except Exception as e:
            logger.debug(f"Collaboration notification failed: {e}")

    def _cache_collaborators(self, ticket_id: int):
        """Cache active collaborators in Redis"""
        try:
            import json
            collaborators = self.get_active_collaborators(ticket_id)
            self.redis.setex(
                f"collaborators:ticket:{ticket_id}",
                600,  # 10 minutes TTL
                json.dumps(collaborators)
            )
        except Exception as e:
            logger.debug(f"Cache collaborators failed: {e}")
