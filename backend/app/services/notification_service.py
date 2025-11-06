#!/usr/bin/env python3
"""
Notification Service - Google Chat, Slack, and other notification channels
"""

from typing import Dict, Optional, List
from datetime import datetime, date
from sqlalchemy.orm import Session
from loguru import logger
import requests
import json

from app.models.ticket import TicketHistory
from app.models.team import TeamMember
from app.models.escalation import Escalation
from app.models.sla import SLATracker
from app.models.schedule import OnCallAssignment
from app.core.config import settings


class NotificationService:
    """Manages notifications across multiple channels"""

    def __init__(self, db: Session):
        self.db = db
        self.google_chat_webhook = settings.GOOGLE_CHAT_WEBHOOK
        self.google_chat_enabled = settings.GOOGLE_CHAT_ENABLED
        self.slack_webhook = settings.SLACK_WEBHOOK
        self.slack_enabled = settings.SLACK_ENABLED
        # Get Redis connection for deduplication
        from app.core.database import get_redis
        self.redis = get_redis()

    def send_assignment_notification(
        self,
        ticket: TicketHistory,
        assignee: TeamMember,
        ai_analysis: str = None
    ) -> bool:
        """Send ticket assignment notification with deduplication"""
        try:
            # NOTIFICATION DEDUPLICATION: Prevent duplicate notifications
            notif_key = f"notification:assignment:{ticket.redmine_ticket_id}:{assignee.id}"

            if self.redis:
                # Atomic operation: Set key only if it doesn't exist
                notification_sent = self.redis.set(
                    notif_key,
                    "sent",
                    nx=True,  # Only set if key doesn't exist (atomic)
                    ex=3600   # Expire in 1 hour (prevent same notification within 1 hour)
                )

                if not notification_sent:
                    logger.info(f"🔔 Notification already sent for ticket #{ticket.redmine_ticket_id} to {assignee.name}, skipping")
                    return True  # Return True since notification was already sent

                logger.debug(f"🔒 Acquired notification lock for ticket #{ticket.redmine_ticket_id}")

            # Build and send message
            message = self._build_assignment_message(ticket, assignee, ai_analysis)

            # Send to enabled channels
            success = True
            if self.google_chat_enabled:
                success &= self._send_google_chat(message)
            if self.slack_enabled:
                success &= self._send_slack(message)

            if success:
                logger.info(f"✅ Assignment notification sent for ticket #{ticket.redmine_ticket_id}")
            else:
                # If sending failed, release the lock so it can be retried
                if self.redis:
                    self.redis.delete(notif_key)
                    logger.warning(f"⚠️ Released notification lock due to send failure")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to send assignment notification: {e}")
            return False

    def send_sla_warning_alert(self, tracker: SLATracker) -> bool:
        """Send SLA warning alert (80% consumed)"""
        try:
            ticket = tracker.ticket
            remaining_minutes = tracker.calculate_time_remaining("resolution")

            message = {
                "text": f"⚠️ *SLA WARNING* - Ticket #{ticket.redmine_ticket_id}",
                "cards": [{
                    "header": {
                        "title": f"⚠️ SLA Warning Alert",
                        "subtitle": f"Ticket #{ticket.redmine_ticket_id} - {remaining_minutes}min remaining"
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "Status",
                                    "content": "80% SLA Time Consumed",
                                    "contentMultiline": False,
                                    "icon": "CLOCK"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Priority",
                                    "content": ticket.priority.value,
                                    "icon": "BOOKMARK"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Assigned To",
                                    "content": ticket.assigned_to.name if ticket.assigned_to else "Unassigned"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Time Remaining",
                                    "content": f"{remaining_minutes} minutes",
                                    "icon": "CLOCK"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": f"<b>Subject:</b> {ticket.subject}"
                                }
                            },
                            {
                                "buttons": [
                                    {
                                        "textButton": {
                                            "text": "VIEW TICKET",
                                            "onClick": {
                                                "openLink": {
                                                    "url": ticket.redmine_url
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }]
                }]
            }

            return self._send_google_chat(message)

        except Exception as e:
            logger.error(f"❌ Failed to send SLA warning: {e}")
            return False

    def send_sla_critical_alert(self, tracker: SLATracker) -> bool:
        """Send SLA critical alert (90% consumed)"""
        try:
            ticket = tracker.ticket
            remaining_minutes = tracker.calculate_time_remaining("resolution")

            message = {
                "text": f"🔴 *SLA CRITICAL* - Ticket #{ticket.redmine_ticket_id}",
                "cards": [{
                    "header": {
                        "title": f"🔴 SLA CRITICAL ALERT",
                        "subtitle": f"Ticket #{ticket.redmine_ticket_id} - {remaining_minutes}min remaining"
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "⚠️ URGENT",
                                    "content": "90% SLA Time Consumed - Immediate Action Required",
                                    "contentMultiline": True,
                                    "icon": "DESCRIPTION"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Priority",
                                    "content": ticket.priority.value,
                                    "icon": "BOOKMARK"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Assigned To",
                                    "content": ticket.assigned_to.name if ticket.assigned_to else "Unassigned"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Time Remaining",
                                    "content": f"⏰ {remaining_minutes} minutes",
                                    "icon": "CLOCK"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": f"<b>Action Required:</b> Escalation recommended if resolution not possible within {remaining_minutes} minutes."
                                }
                            },
                            {
                                "buttons": [
                                    {
                                        "textButton": {
                                            "text": "VIEW TICKET",
                                            "onClick": {
                                                "openLink": {
                                                    "url": ticket.redmine_url
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }]
                }]
            }

            return self._send_google_chat(message)

        except Exception as e:
            logger.error(f"❌ Failed to send SLA critical alert: {e}")
            return False

    def send_sla_breach_alert(self, ticket: TicketHistory) -> bool:
        """Send SLA breach alert"""
        try:
            message = {
                "text": f"🚨 *SLA BREACH* - Ticket #{ticket.redmine_ticket_id}",
                "cards": [{
                    "header": {
                        "title": f"🚨 SLA BREACH",
                        "subtitle": f"Ticket #{ticket.redmine_ticket_id} has breached SLA"
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "🚨 BREACH ALERT",
                                    "content": f"SLA breached by {ticket.sla_breach_minutes} minutes",
                                    "contentMultiline": True,
                                    "icon": "DESCRIPTION"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Priority",
                                    "content": ticket.priority.value
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Environment",
                                    "content": ticket.environment or "Not specified"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Assigned To",
                                    "content": ticket.assigned_to.name if ticket.assigned_to else "Unassigned"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": f"<b>Subject:</b> {ticket.subject}"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": "<b>Action:</b> Automatic escalation has been triggered."
                                }
                            },
                            {
                                "buttons": [
                                    {
                                        "textButton": {
                                            "text": "VIEW TICKET",
                                            "onClick": {
                                                "openLink": {
                                                    "url": ticket.redmine_url
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }]
                }]
            }

            return self._send_google_chat(message)

        except Exception as e:
            logger.error(f"❌ Failed to send SLA breach alert: {e}")
            return False

    def send_escalation_notification(
        self,
        ticket: TicketHistory,
        escalation: Escalation,
        new_assignee: TeamMember
    ) -> bool:
        """Send escalation notification"""
        try:
            message = {
                "text": f"🔼 *TICKET ESCALATED* - #{ticket.redmine_ticket_id}",
                "cards": [{
                    "header": {
                        "title": f"🔼 Ticket Escalated",
                        "subtitle": f"Ticket #{ticket.redmine_ticket_id} escalated to {escalation.to_team_level}"
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "Escalation Path",
                                    "content": f"{escalation.from_team_level} → {escalation.to_team_level}",
                                    "icon": "STAR"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Reason",
                                    "content": escalation.reason.value.replace('_', ' ').title()
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "New Assignee",
                                    "content": new_assignee.name,
                                    "icon": "PERSON"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Priority",
                                    "content": ticket.priority.value
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": f"<b>Subject:</b> {ticket.subject}"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": f"<b>Description:</b> {escalation.description}"
                                }
                            },
                            {
                                "buttons": [
                                    {
                                        "textButton": {
                                            "text": "VIEW TICKET",
                                            "onClick": {
                                                "openLink": {
                                                    "url": ticket.redmine_url
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }]
                }]
            }

            return self._send_google_chat(message)

        except Exception as e:
            logger.error(f"❌ Failed to send escalation notification: {e}")
            return False

    def send_oncall_rotation_summary(
        self,
        week_start: date,
        assignments: List[OnCallAssignment],
        rotation_links: Dict[str, Optional[str]],
    ) -> bool:
        if not assignments or not self.google_chat_enabled or not self.google_chat_webhook:
            return False

        week_label = week_start.strftime("%d %b %Y")
        widgets: List[Dict] = []

        for assignment in assignments:
            team_label = assignment.team_level
            member = assignment.team_member
            member_name = member.name if member else "Unassigned"
            details = [member_name]
            if member and member.timezone:
                details.append(f"Timezone: {member.timezone}")

            widgets.append({
                "keyValue": {
                    "topLabel": f"{team_label} On-Call",
                    "content": "\n".join(details),
                    "contentMultiline": True,
                }
            })

            rotate_link = rotation_links.get(team_label)
            if rotate_link:
                widgets.append({
                    "buttons": [{
                        "textButton": {
                            "text": f"ROTATE {team_label}",
                            "onClick": {
                                "openLink": {
                                    "url": rotate_link
                                }
                            }
                        }
                    }]
                })

        message = {
            "cards": [{
                "header": {
                    "title": "📟 Weekly On-Call Roster",
                    "subtitle": f"Week of {week_label}"
                },
                "sections": [{"widgets": widgets}]
            }]
        }

        return self._send_google_chat(message)

    def send_oncall_rotation_update(
        self,
        week_start: date,
        replacement: OnCallAssignment,
        previous: OnCallAssignment,
        reason: Optional[str],
        rotation_links: Dict[str, Optional[str]],
    ) -> bool:
        if not self.google_chat_enabled or not self.google_chat_webhook:
            return False

        member_name = replacement.team_member.name if replacement.team_member else "Unassigned"
        previous_name = previous.team_member.name if previous.team_member else "Unassigned"
        reason_text = reason or "No reason provided"
        rotate_link = rotation_links.get(replacement.team_level)

        widgets: List[Dict] = [
            {
                "textParagraph": {
                    "text": (
                        f"<b>{replacement.team_level} On-Call Update</b><br>"
                        f"Replacement: {member_name}<br>"
                        f"Previous: {previous_name}<br>"
                        f"Reason: {reason_text}"
                    )
                }
            }
        ]

        if rotate_link:
            widgets.append({
                "buttons": [{
                    "textButton": {
                        "text": "ROTATE AGAIN",
                        "onClick": {
                            "openLink": {
                                "url": rotate_link
                            }
                        }
                    }
                }]
            })

        message = {
            "cards": [{
                "header": {
                    "title": "🔄 On-Call Rotation Update",
                    "subtitle": week_start.strftime("Week of %d %b %Y")
                },
                "sections": [{"widgets": widgets}]
            }]
        }

        return self._send_google_chat(message)

    def send_daily_summary(self, summary_data: Dict) -> bool:
        """Send daily team performance summary"""
        try:
            message = {
                "text": f"📊 *Daily Summary* - {datetime.now().strftime('%Y-%m-%d')}",
                "cards": [{
                    "header": {
                        "title": "📊 DevOps Team Daily Summary",
                        "subtitle": datetime.now().strftime('%A, %B %d, %Y')
                    },
                    "sections": [{
                        "widgets": [
                            {
                                "keyValue": {
                                    "topLabel": "Tickets Processed",
                                    "content": str(summary_data.get('total_processed', 0)),
                                    "icon": "TICKET"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Tickets Resolved",
                                    "content": str(summary_data.get('total_resolved', 0)),
                                    "icon": "CONFIRMATION_NUMBER_ICON"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "SLA Compliance",
                                    "content": f"{summary_data.get('sla_compliance_rate', 0):.1f}%",
                                    "icon": "CLOCK"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Avg Resolution Time",
                                    "content": f"{summary_data.get('avg_resolution_hours', 0):.1f} hours"
                                }
                            },
                            {
                                "keyValue": {
                                    "topLabel": "Escalations",
                                    "content": str(summary_data.get('escalations_count', 0)),
                                    "icon": "STAR"
                                }
                            },
                            {
                                "textParagraph": {
                                    "text": "<b>Top Performers:</b><br>" + "<br>".join([
                                        f"• {p['name']}: {p['resolved']} tickets"
                                        for p in summary_data.get('top_performers', [])[:5]
                                    ])
                                }
                            }
                        ]
                    }]
                }]
            }

            return self._send_google_chat(message)

        except Exception as e:
            logger.error(f"❌ Failed to send daily summary: {e}")
            return False

    def _build_assignment_message(
        self,
        ticket: TicketHistory,
        assignee: TeamMember,
        ai_analysis: str
    ) -> Dict:
        """Build rich card message for ticket assignment"""
        env_emoji = {
            'prod': '🔴',
            'production': '🔴',
            'staging': '🟠',
            'dev': '🟡',
            'development': '🟡'
        }.get(ticket.environment.lower() if ticket.environment else '', '🔵')

        priority_emoji = {
            'P1(Critical)': '🔴',
            'P2(High)': '🟠',
            'P3(Medium)': '🟡',
            'P4(Low)': '🟢',
            'P5(Trivial)': '⚪'
        }.get(ticket.priority.value, '🔵')

        # Truncate AI analysis if too long
        analysis_preview = (ai_analysis[:300] + '...') if ai_analysis and len(ai_analysis) > 300 else ai_analysis

        message = {
            "text": f"🎫 *New Ticket Assigned* - #{ticket.redmine_ticket_id}",
            "cards": [{
                "header": {
                    "title": f"🎫 Ticket #{ticket.redmine_ticket_id} Assigned",
                    "subtitle": f"{priority_emoji} {ticket.priority.value} - {env_emoji} {ticket.environment or 'Not specified'}"
                },
                "sections": [{
                    "widgets": [
                        {
                            "keyValue": {
                                "topLabel": "Assigned To",
                                "content": f"{assignee.name} ({assignee.team_level})",
                                "icon": "PERSON"
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Priority",
                                "content": ticket.priority.value,
                                "icon": "BOOKMARK"
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Environment",
                                "content": ticket.environment or "Not specified",
                                "icon": "DESCRIPTION"
                            }
                        },
                        {
                            "keyValue": {
                                "topLabel": "Category",
                                "content": ticket.category.value if ticket.category else "Not categorized"
                            }
                        },
                        {
                            "textParagraph": {
                                "text": f"<b>Subject:</b> {ticket.subject}"
                            }
                        }
                    ]
                }]
            }]
        }

        # Add AI analysis section if available
        if analysis_preview:
            message["cards"][0]["sections"].append({
                "widgets": [
                    {
                        "textParagraph": {
                            "text": f"<b>AI Analysis:</b><br>{analysis_preview}"
                        }
                    }
                ]
            })

        # Add action buttons
        message["cards"][0]["sections"].append({
            "widgets": [
                {
                    "buttons": [
                        {
                            "textButton": {
                                "text": "VIEW TICKET",
                                "onClick": {
                                    "openLink": {
                                        "url": ticket.redmine_url
                                    }
                                }
                            }
                        }
                    ]
                }
            ]
        })

        return message

    def _send_google_chat(self, message: Dict) -> bool:
        """Send message to Google Chat"""
        try:
            if not self.google_chat_enabled or not self.google_chat_webhook:
                logger.debug("Google Chat not enabled or webhook not configured")
                return False

            response = requests.post(
                self.google_chat_webhook,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                logger.debug("✅ Google Chat message sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Google Chat failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Google Chat send error: {e}")
            return False

    def _send_slack(self, message: Dict) -> bool:
        """Send message to Slack"""
        try:
            if not self.slack_enabled or not self.slack_webhook:
                return False

            # Convert Google Chat format to Slack format
            slack_message = self._convert_to_slack_format(message)

            response = requests.post(
                self.slack_webhook,
                json=slack_message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                logger.debug("✅ Slack message sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Slack failed: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Slack send error: {e}")
            return False

    def _convert_to_slack_format(self, google_chat_message: Dict) -> Dict:
        """Convert Google Chat message format to Slack format"""
        # Simple conversion - can be enhanced
        text = google_chat_message.get('text', '')
        return {
            "text": text,
            "mrkdwn": True
        }
