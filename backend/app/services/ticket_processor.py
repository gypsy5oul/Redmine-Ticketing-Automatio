#!/usr/bin/env python3
"""
Ticket Processor - Main orchestration pipeline
Coordinates all services to process tickets end-to-end
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from loguru import logger
import requests
import hashlib
import pytz

from app.models.ticket import TicketHistory, TicketStatus, TicketPriority, TicketCategory, ComplexityLevel
from app.models.team import TeamMember
from app.models.sla import SLATracker, SLAStatus
from app.services.llm_service import EnhancedLLMService
from app.services.ml_service import MLPredictionService
from app.services.sla_manager import SLAManager
from app.services.workload_manager import WorkloadManager
from app.services.escalation_service import EscalationService
from app.services.notification_service import NotificationService
from app.services.redmine_service import RedmineService
from app.services.work_session_service import WorkSessionService
from app.core.config import settings
from app.core.database import get_redis


class TicketProcessor:
    """Main ticket processing pipeline"""

    def __init__(self, db: Session):
        self.db = db
        self.llm_service = EnhancedLLMService(db)  # Pass db for ML integration
        self.ml_service = MLPredictionService(db)
        self.sla_manager = SLAManager(db)
        self.workload_manager = WorkloadManager(db)
        self.escalation_service = EscalationService(db)
        self.notification_service = NotificationService(db)
        self.redmine_service = RedmineService()
        self.redis = get_redis()
        self.work_session_service = WorkSessionService(db)
        self._priority_aliases = {
            "P1(Critical)": "P1(Critical)",
            "P1": "P1(Critical)",
            "CRITICAL": "P1(Critical)",
            "P2(High)": "P2(High)",
            "P2": "P2(High)",
            "HIGH": "P2(High)",
            "P3(Medium)": "P3(Medium)",
            "P3": "P3(Medium)",
            "MEDIUM": "P3(Medium)",
            "P4(Low)": "P4(Low)",
            "P4": "P4(Low)",
            "LOW": "P4(Low)",
            "NORMAL": "P4(Low)",
            "P4(NORMAL)": "P4(Low)",
            "P4NORMAL": "P4(Low)",
            "P4(Normal)": "P4(Low)",
            "P5(Trivial)": "P5(Trivial)",
            "P5": "P5(Trivial)",
            "TRIVIAL": "P5(Trivial)",
        }

    def process_new_tickets(self) -> Dict:
        """
        Main processing pipeline - fetches and processes all new tickets

        Returns:
            {
                "success": bool,
                "processed": int,
                "assigned": int,
                "errors": [],
                "tickets": [...]
            }
        """
        try:
            logger.info("🚀 Starting ticket processing pipeline...")

            # 1. Fetch new tickets from Redmine
            new_tickets = self._fetch_new_tickets_from_redmine()

            if not new_tickets:
                logger.info("📭 No new tickets to process")
                return {
                    "success": True,
                    "processed": 0,
                    "assigned": 0,
                    "errors": [],
                    "tickets": []
                }

            logger.info(f"📋 Found {len(new_tickets)} new tickets to process")

            processed_tickets = []
            errors = []
            assigned_count = 0

            # 2. Process each ticket through the pipeline
            for redmine_ticket in new_tickets:
                try:
                    result = self._process_single_ticket(redmine_ticket)
                    processed_tickets.append(result)

                    if result.get('assigned'):
                        assigned_count += 1

                except Exception as e:
                    error_msg = f"Ticket #{redmine_ticket.get('id')}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    errors.append(error_msg)

            logger.info(
                f"✅ Pipeline completed: {len(processed_tickets)} processed, "
                f"{assigned_count} assigned, {len(errors)} errors"
            )

            return {
                "success": True,
                "processed": len(processed_tickets),
                "assigned": assigned_count,
                "errors": errors,
                "tickets": processed_tickets
            }

        except Exception as e:
            logger.error(f"💥 Pipeline failed: {e}")
            return {
                "success": False,
                "processed": 0,
                "assigned": 0,
                "errors": [str(e)],
                "tickets": []
            }

    def _process_single_ticket(self, redmine_ticket: Dict) -> Dict:
        """
        Process a single ticket through the complete pipeline

        Pipeline stages:
        1. Extract ticket data
        2. Analyze priority and environment
        3. AI analysis with LLM
        4. Smart routing with ML
        5. Create/update ticket in database
        6. Start SLA tracking
        7. Update Redmine
        8. Send notifications

        Returns:
            Processing result dictionary
        """
        ticket_id = redmine_ticket['id']
        lock_key = f"ticket:processing:lock:{ticket_id}"

        # DISTRIBUTED LOCK: Prevent multiple workers from processing the same ticket
        if self.redis:
            try:
                lock_acquired = self.redis.set(
                    lock_key,
                    "processing",
                    nx=True,  # Only set if key doesn't exist (atomic operation)
                    ex=300    # Lock expires in 5 minutes (safety mechanism)
                )

                if not lock_acquired:
                    logger.info(f"🔒 Ticket #{ticket_id} is already being processed by another worker, skipping")
                    return {
                        "ticket_id": ticket_id,
                        "assigned": False,
                        "reason": "Already being processed by another worker",
                        "skipped": True
                    }
            except Exception as redis_error:
                logger.warning(f"⚠️ Redis lock failed for ticket #{ticket_id}: {redis_error}. Continuing without lock...")
                # Continue processing without distributed lock if Redis fails

        logger.info(f"🎫 Processing ticket #{ticket_id}: {redmine_ticket.get('subject', '')[:50]}")

        try:
            # Stage 1: Extract and normalize ticket data
            ticket_data = self._extract_ticket_data(redmine_ticket)

            # Stage 2: Analyze priority and environment
            priority_info = self._analyze_priority(ticket_data)
            ticket_data.update(priority_info)

            # Stage 3: AI Analysis with LLM
            logger.info(f"🤖 Running AI analysis for ticket #{ticket_id}")
            ai_analysis = self.llm_service.analyze_ticket(ticket_data)
            ai_analysis["classification"] = self._sanitize_classification(
                ai_analysis.get("classification", {}),
                ticket_data
            )

            # Stage 4: Smart routing with ML
            logger.info(f"🎯 Finding best assignee for ticket #{ticket_id}")
            assignee, routing_info = self._find_best_assignee(
                ticket_data,
                ai_analysis['classification']['category']
            )

            # Debug logging
            logger.debug(f"DEBUG: assignee={assignee}, routing_info={routing_info}")

            if not assignee:
                reason_message = routing_info.get("message", "No available team members")
                logger.warning(f"⚠️ Ticket #{ticket_id} not assigned ({reason_message})")
                return {
                    "ticket_id": ticket_id,
                    "assigned": False,
                    "reason": reason_message,
                    "error": routing_info.get("error", "No capacity available"),
                    "deferred": routing_info.get("deferred", False)
                }

            # Stage 5: Create ticket record in database
            db_ticket = self._create_ticket_record(ticket_data, ai_analysis, assignee)

            # Stage 6: Start SLA tracking
            logger.info(f"⏱️ Starting SLA tracking for ticket #{ticket_id}")
            self.sla_manager.start_sla_tracking(
                ticket_id=db_ticket.id,
                priority=ticket_data['adjusted_priority'],
                environment=ticket_data['environment']
            )

            # Stage 7: Update Redmine with assignment and AI analysis
            logger.info(f"📝 Updating Redmine for ticket #{ticket_id}")
            self._update_redmine_ticket(
                ticket_id,
                assignee,
                ai_analysis['initial_response'],
                ticket_data
            )

            # Stage 8: Send notifications
            logger.info(f"🔔 Sending notifications for ticket #{ticket_id}")
            self.notification_service.send_assignment_notification(
                db_ticket,
                assignee,
                ai_analysis['initial_response']
            )

            # Update workload cache
            self.workload_manager.increment_workload(assignee.id)

            logger.info(f"✅ Successfully processed ticket #{ticket_id} → {assignee.name}")

            return {
                "ticket_id": ticket_id,
                "redmine_ticket_id": db_ticket.redmine_ticket_id,
                "subject": db_ticket.subject,
                "assigned": True,
                "assignee": {
                    "id": assignee.id,
                    "name": assignee.name,
                    "team_level": assignee.team_level
                },
                "priority": {
                    "original": ticket_data['original_priority'],
                    "adjusted": ticket_data['adjusted_priority'],
                    "downgraded": ticket_data['priority_adjusted']
                },
                "category": ai_analysis['classification']['category'],
                "complexity": ai_analysis['classification']['complexity'],
                "routing": routing_info,
                "ai_analysis_preview": ai_analysis['initial_response'][:200] + "..."
            }

        except Exception as e:
            logger.error(f"❌ Error processing ticket #{ticket_id}: {e}")
            raise

        finally:
            # RELEASE DISTRIBUTED LOCK: Always release the lock when done
            if self.redis:
                try:
                    self.redis.delete(lock_key)
                    logger.debug(f"🔓 Released processing lock for ticket #{ticket_id}")
                except Exception as lock_error:
                    logger.warning(f"⚠️ Failed to release lock for ticket #{ticket_id}: {lock_error}")

    def _fetch_new_tickets_from_redmine(self) -> List[Dict]:
        """Fetch new tickets from Redmine API"""
        try:
            tickets = self.redmine_service.get_new_issues(
                project_id=settings.DEVOPS_PROJECT_ID,
                limit=50
            )
            logger.info(f"📥 Fetched {len(tickets)} new tickets from Redmine")
            return tickets

        except Exception as e:
            logger.error(f"❌ Failed to fetch tickets from Redmine: {e}")
            return []

    def _extract_ticket_data(self, redmine_ticket: Dict) -> Dict:
        """Extract and normalize ticket data"""
        custom_fields = {
            cf['name']: cf.get('value', '')
            for cf in redmine_ticket.get('custom_fields', [])
        }

        project_jira_id_raw = custom_fields.get('Project Jira ID', '')
        if isinstance(project_jira_id_raw, dict):
            project_jira_id_raw = project_jira_id_raw.get('value', '')

        project_jira_id = (project_jira_id_raw or "").strip() or None

        raw_priority = redmine_ticket['priority']['name']
        normalized_priority = self._normalize_priority_label(raw_priority)

        return {
            "id": redmine_ticket['id'],
            "subject": redmine_ticket.get('subject', ''),
            "description": redmine_ticket.get('description', ''),
            "original_priority": normalized_priority,
            "environment": custom_fields.get('Deployment Environment Tags', '').lower().strip(),
            "project_jira_id": project_jira_id,
            "redmine_url": f"{settings.REDMINE_BASE_URL}/issues/{redmine_ticket['id']}",
            "requestor_name": redmine_ticket.get('author', {}).get('name', 'Customer')
        }

    def _analyze_priority(self, ticket_data: Dict) -> Dict:
        """
        Analyze and adjust priority based on environment

        P1 (Critical) only for production environments
        """
        original_priority = ticket_data['original_priority']
        environment = ticket_data['environment']

        # Priority ID mapping
        priority_ids = {
            'P1(Critical)': 4,
            'P2(High)': 5,
            'P3(Medium)': 3,
            'P4(Low)': 2,
            'P5(Trivial)': 1
        }

        adjusted_priority = original_priority
        priority_adjusted = False

        # Check if P1 should be downgraded
        if original_priority == 'P1(Critical)':
            is_production = any(
                env in environment
                for env in ['prod', 'production', 'live']
            )

            if not is_production:
                adjusted_priority = 'P2(High)'
                priority_adjusted = True
                logger.info(
                    f"🔄 Priority adjusted: {original_priority} → {adjusted_priority} "
                    f"(Environment: {environment})"
                )

        return {
            "original_priority": original_priority,
            "adjusted_priority": adjusted_priority,
            "priority_adjusted": priority_adjusted,
            "priority_id": priority_ids.get(adjusted_priority, 3)
        }

    def _normalize_priority_label(self, priority_name: str) -> str:
        """Normalize Redmine priority labels to internal Enum values"""
        if not priority_name:
            logger.warning("Priority missing from ticket — defaulting to P3(Medium)")
            return "P3(Medium)"

        cleaned = priority_name.strip()
        direct_hit = self._priority_aliases.get(cleaned)
        if direct_hit:
            return direct_hit

        compact = cleaned.replace(" ", "").replace("-", "").upper()
        direct_hit = self._priority_aliases.get(compact)
        if direct_hit:
            return direct_hit

        upper = cleaned.upper()
        direct_hit = self._priority_aliases.get(upper)
        if direct_hit:
            return direct_hit

        logger.warning(
            f"Unknown priority label '{priority_name}', defaulting to P3(Medium)"
        )
        return "P3(Medium)"

    def _find_best_assignee(
        self,
        ticket_data: Dict,
        category: str
    ) -> tuple[Optional[TeamMember], Dict]:
        """Find best assignee using ML-based routing"""
        try:
            # Determine team level based on priority
            priority = ticket_data['adjusted_priority']

            if priority == 'P1(Critical)':
                team_level = "L2"  # Critical tickets go to L2
            else:
                team_level = "L1"  # Others start at L1

            if self._should_delay_for_business_hours(priority):
                return None, {
                    "error": "deferred_off_hours",
                    "deferred": True,
                    "message": "Outside business hours; routing deferred until next business window"
                }

            # Get available members
            available_members = self.workload_manager.get_available_members(team_level)

            if not available_members:
                logger.warning(f"No available {team_level} members, checking next level")
                # Try next level
                if team_level == "L1":
                    available_members = self.workload_manager.get_available_members("L2")
                    team_level = "L2"

            if not available_members:
                return None, {"error": "No available team members"}

            # Use ML service for smart routing
            best_assignee, confidence, reasons = self.ml_service.smart_route_ticket(
                ticket_data,
                available_members,
                category
            )

            routing_info = {
                "team_level": team_level,
                "confidence": round(confidence, 2),
                "reasons": reasons,
                "candidates_evaluated": len(available_members)
            }

            return best_assignee, routing_info

        except Exception as e:
            logger.error(f"❌ Error finding assignee: {e}")
            return None, {"error": str(e)}

    def _should_delay_for_business_hours(self, priority: str) -> bool:
        """Return True if ticket should wait until business hours for assignment."""
        if priority == "P1(Critical)":
            return False

        tz = pytz.timezone(settings.BUSINESS_TIMEZONE)
        local_now = datetime.now(tz)

        if local_now.weekday() not in settings.BUSINESS_DAYS:
            return True

        start = settings.BUSINESS_HOURS_START
        end = settings.BUSINESS_HOURS_END
        return not (start <= local_now.hour < end)

    def _sanitize_classification(self, classification: Dict, ticket_data: Dict) -> Dict:
        """Ensure classification keys map to known enums with safe defaults."""
        fallback = self.llm_service._rule_based_classification(ticket_data)

        # Category normalisation
        category_aliases = {
            "ci/cd": "cicd",
            "ci_cd": "cicd",
            "ci-cd": "cicd",
            "continuous_integration": "cicd",
            "messaging_queue": "messaging",
            "message_queue": "messaging",
            "k8s": "kubernetes",
        }

        raw_category = str(classification.get("category") or "").lower().strip()
        normalized_category = category_aliases.get(raw_category, raw_category)
        allowed_categories = {cat.value for cat in TicketCategory}
        if normalized_category not in allowed_categories:
            normalized_category = fallback["category"]

        # Complexity normalisation
        complexity_aliases = {
            "high": "complex",
            "medium": "moderate",
            "low": "simple",
            "very_high": "critical",
        }

        raw_complexity = str(classification.get("complexity") or "").lower().strip()
        normalized_complexity = complexity_aliases.get(raw_complexity, raw_complexity)
        allowed_complexities = {level.value for level in ComplexityLevel}
        if normalized_complexity not in allowed_complexities:
            normalized_complexity = fallback["complexity"]

        # Estimated effort
        try:
            estimated_hours = float(classification.get("estimated_hours", fallback["estimated_hours"]))
            if estimated_hours <= 0:
                raise ValueError
        except (ValueError, TypeError):
            estimated_hours = fallback["estimated_hours"]

        return {
            "category": normalized_category,
            "complexity": normalized_complexity,
            "estimated_hours": estimated_hours,
            "required_skills": classification.get("required_skills", fallback.get("required_skills", [])),
            "urgency_factors": classification.get("urgency_factors", fallback.get("urgency_factors", [])),
            "similar_patterns": classification.get("similar_patterns", fallback.get("similar_patterns", [])),
        }

    def _create_ticket_record(
        self,
        ticket_data: Dict,
        ai_analysis: Dict,
        assignee: TeamMember
    ) -> TicketHistory:
        """Create ticket record in database"""
        try:
            classification = ai_analysis['classification']

            existing = self.db.query(TicketHistory).filter(
                TicketHistory.redmine_ticket_id == ticket_data['id']
            ).first()

            now_utc = datetime.now(timezone.utc)

            if existing:
                logger.info(
                    f"♻️ Ticket #{ticket_data['id']} already exists. Updating assignment "
                    f"to {assignee.name}"
                )
                previous_assignee = existing.assigned_to_id
                existing.assigned_to_id = assignee.id
                existing.team_level = assignee.team_level
                existing.priority = TicketPriority(ticket_data['adjusted_priority'])
                existing.original_priority = TicketPriority(ticket_data['original_priority'])
                existing.priority_adjusted = ticket_data['priority_adjusted']
                existing.status = TicketStatus.ASSIGNED
                existing.environment = ticket_data['environment']
                existing.category = TicketCategory(classification['category'])
                existing.complexity = ComplexityLevel(classification['complexity'])
                existing.estimated_resolution_hours = classification['estimated_hours']
                existing.ai_analysis = ai_analysis['initial_response']
                existing.ai_model_used = settings.LLM_MODEL
                existing.requester_name = ticket_data.get('requestor_name')
                existing.assigned_at = now_utc
                existing.updated_at = now_utc

                self.db.commit()
                self.db.refresh(existing)

                try:
                    if previous_assignee != assignee.id:
                        self.work_session_service.handle_assignment_change(
                            existing,
                            assignee.id,
                            previous_assignee,
                        )
                    else:
                        self.work_session_service.ensure_idle_session(existing.id, assignee.id)
                except Exception as tracking_error:
                    logger.warning(
                        "⚠️ Work session update failed for ticket %s reassignment: %s",
                        existing.id,
                        tracking_error,
                    )

                # Record performance metrics for ticket reassignment
                try:
                    from app.services.performance_tracker import PerformanceTracker
                    performance_tracker = PerformanceTracker(self.db)
                    performance_tracker.record_ticket_assignment(existing)
                except Exception as perf_error:
                    logger.warning(f"⚠️ Failed to record performance metric: {perf_error}")

                return existing

            ticket = TicketHistory(
                redmine_ticket_id=ticket_data['id'],
                subject=ticket_data['subject'],
                description=ticket_data['description'],
                assigned_to_id=assignee.id,
                team_level=assignee.team_level,
                priority=TicketPriority(ticket_data['adjusted_priority']),
                original_priority=TicketPriority(ticket_data['original_priority']),
                priority_adjusted=ticket_data['priority_adjusted'],
                status=TicketStatus.ASSIGNED,
                environment=ticket_data['environment'],
                category=TicketCategory(classification['category']),
                complexity=ComplexityLevel(classification['complexity']),
                estimated_resolution_hours=classification['estimated_hours'],
                ai_analysis=ai_analysis['initial_response'],
                ai_model_used=settings.LLM_MODEL,
                redmine_url=ticket_data['redmine_url'],
                project_jira_id=ticket_data['project_jira_id'],
                requester_name=ticket_data.get('requestor_name'),
                assigned_at=now_utc
            )

            self.db.add(ticket)
            self.db.commit()
            self.db.refresh(ticket)

            try:
                self.work_session_service.handle_assignment_change(ticket, assignee.id, None)
            except Exception as tracking_error:
                logger.warning(
                    "⚠️ Failed to initialize work session tracking for ticket %s: %s",
                    ticket.id,
                    tracking_error,
                )

            # Record performance metrics for ticket assignment
            try:
                from app.services.performance_tracker import PerformanceTracker
                performance_tracker = PerformanceTracker(self.db)
                performance_tracker.record_ticket_assignment(ticket)
            except Exception as perf_error:
                logger.warning(f"⚠️ Failed to record performance metric: {perf_error}")

            logger.info(f"✅ Created database record for ticket #{ticket.redmine_ticket_id}")
            return ticket

        except Exception as e:
            logger.error(f"❌ Failed to create ticket record: {e}")
            self.db.rollback()
            raise

    def _update_redmine_ticket(
        self,
        ticket_id: int,
        assignee: TeamMember,
        ai_response: str,
        ticket_data: Dict
    ):
        """Update Redmine with assignment and AI analysis"""
        try:
            # Build assignment note with AI analysis
            note = f"""🎫 AUTOMATED TICKET ASSIGNMENT

**Assigned To:** {assignee.name} ({assignee.team_level})

**AI ANALYSIS & INITIAL RESPONSE:**

{ai_response}

**NEXT STEPS:**
• Your assigned SPOC will investigate and provide updates
• Add any additional information as comments
• Contact your SPOC via Google Chat for urgent matters

---
🤖 DevOps Automation System v3.0
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            # Add priority adjustment note if needed
            if ticket_data['priority_adjusted']:
                priority_note = f"""

**PRIORITY ADJUSTMENT NOTICE:**

This ticket was adjusted from {ticket_data['original_priority']} to {ticket_data['adjusted_priority']} based on environment analysis.

• Environment: {ticket_data['environment']}
• Reason: P1 (Critical) priority is reserved for production environment incidents

If this is a production issue, please update the environment tag and we'll re-prioritize accordingly."""
                note += priority_note

            # ATOMIC NOTE DEDUPLICATION: Use SETNX to prevent duplicate notes
            note_hash = hashlib.sha256(note.encode("utf-8")).hexdigest()
            cache_key = f"ticket:note-hash:{ticket_id}:{assignee.id}"

            if self.redis:
                try:
                    # Atomic operation: Set key only if it doesn't exist
                    note_added = self.redis.set(
                        cache_key,
                        note_hash,
                        nx=True,      # Only set if key doesn't exist (SETNX - atomic)
                        ex=86400      # Expire in 24 hours
                    )

                    if not note_added:
                        # Another worker already added this note
                        logger.info(f"ℹ️ Skipping Redmine update for ticket #{ticket_id} (note already added by another worker)")
                        return

                    logger.debug(f"🔒 Acquired note lock for ticket #{ticket_id}")
                except Exception as redis_error:
                    logger.warning(f"⚠️ Redis note cache failed for ticket #{ticket_id}: {redis_error}. Continuing without cache...")
                    # Continue with Redmine update if Redis cache fails

            # Update issue: assign, change status to "In Progress", and add AI analysis note
            success = self.redmine_service.update_issue(
                issue_id=ticket_id,
                assigned_to_id=assignee.redmine_user_id,
                status_id=2,  # 2 = In Progress
                notes=note
            )

            if success:
                logger.info(f"✅ Updated Redmine ticket #{ticket_id} - Status: In Progress, Assigned: {assignee.name}")
            else:
                logger.warning(f"⚠️ Redmine update failed for ticket #{ticket_id}")

        except Exception as e:
            logger.error(f"❌ Failed to update Redmine: {e}")

    def _parse_redmine_datetime(self, value: Optional[str]) -> Optional[datetime]:
        """Parse Redmine datetime strings into timezone-aware datetimes."""
        if not value:
            return None

        try:
            sanitized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(sanitized)
            if not parsed.tzinfo:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            logger.debug(f"⚠️ Unable to parse Redmine datetime '{value}', defaulting to UTC now")
            return datetime.now(timezone.utc)

    def _map_redmine_status(self, status_name: Optional[str]) -> Optional[TicketStatus]:
        """Map Redmine status labels to internal ticket statuses."""
        if not status_name:
            return None

        normalized = status_name.strip().lower()
        mapping = {
            "new": TicketStatus.NEW,
            "assigned": TicketStatus.ASSIGNED,
            "in progress": TicketStatus.IN_PROGRESS,
            "in-progress": TicketStatus.IN_PROGRESS,
            "pending": TicketStatus.PENDING,
            "feedback": TicketStatus.PENDING,
            "resolved": TicketStatus.RESOLVED,
            "closed": TicketStatus.CLOSED,
            "reopened": TicketStatus.REOPENED,
        }
        return mapping.get(normalized)

    def sync_ticket_statuses_with_redmine(self) -> Dict:
        """Synchronize local ticket statuses with Redmine."""
        try:
            active_statuses = [
                TicketStatus.NEW,
                TicketStatus.ASSIGNED,
                TicketStatus.IN_PROGRESS,
                TicketStatus.PENDING,
                TicketStatus.REOPENED,
            ]

            tickets = self.db.query(TicketHistory).filter(
                TicketHistory.status.in_(active_statuses)
            ).all()

            if not tickets:
                return {"success": True, "updated": 0, "closed": 0, "reopened": 0, "assignment_updates": 0}

            ticket_map = {ticket.redmine_ticket_id: ticket for ticket in tickets if ticket.redmine_ticket_id}
            issues = self.redmine_service.get_issues_by_ids(list(ticket_map.keys()))

            updated = 0
            closed_count = 0
            reopened_count = 0
            assignment_updates = 0

            member_cache: Dict[int, Optional[TeamMember]] = {}

            for issue_id, ticket in ticket_map.items():
                issue = issues.get(issue_id)
                if not issue:
                    continue

                redmine_status = issue.get('status', {}).get('name')
                mapped_status = self._map_redmine_status(redmine_status)

                if mapped_status and mapped_status != ticket.status:
                    if mapped_status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                        timestamp = self._parse_redmine_datetime(issue.get('closed_on')) or self._parse_redmine_datetime(issue.get('updated_on'))
                        ticket.resolved_at = timestamp
                        if mapped_status == TicketStatus.CLOSED:
                            ticket.closed_at = timestamp
                        closed_count += 1
                        self.sla_manager.mark_resolution_completed(ticket.id)
                    elif mapped_status == TicketStatus.REOPENED:
                        ticket.resolved_at = None
                        ticket.closed_at = None
                        reopened_count += 1

                    ticket.status = mapped_status
                    updated += 1

                # Sync assignment information
                assigned_to = issue.get('assigned_to')
                if assigned_to and assigned_to.get('id'):
                    rm_member_id = assigned_to['id']
                    if rm_member_id not in member_cache:
                        member_cache[rm_member_id] = self.db.query(TeamMember).filter(TeamMember.redmine_user_id == rm_member_id).first()
                    member = member_cache[rm_member_id]
                    if member:
                        if ticket.assigned_to_id != member.id:
                            ticket.assigned_to_id = member.id
                            ticket.team_level = member.team_level.value if hasattr(member.team_level, 'value') else member.team_level
                            assignment_updates += 1
                elif ticket.assigned_to_id is not None:
                    ticket.assigned_to_id = None
                    assignment_updates += 1

            if updated or assignment_updates:
                self.db.commit()
            else:
                self.db.rollback()

            return {
                "success": True,
                "total": len(ticket_map),
                "updated": updated,
                "closed": closed_count,
                "reopened": reopened_count,
                "assignment_updates": assignment_updates,
            }

        except Exception as e:
            logger.error(f"❌ Failed to sync ticket statuses: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def process_sla_checks(self) -> Dict:
        """Check and update SLA status for all active tickets"""
        try:
            logger.info("⏱️ Running SLA status checks...")

            active_tickets = self.db.query(TicketHistory).filter(
                TicketHistory.status.in_([
                    TicketStatus.ASSIGNED,
                    TicketStatus.IN_PROGRESS
                ])
            ).all()

            checked = 0
            warnings = 0
            critical = 0
            breaches = 0

            for ticket in active_tickets:
                tracker = self.sla_manager.update_sla_status(ticket.id)

                if tracker:
                    checked += 1
                    if tracker.status == SLAStatus.AT_RISK:
                        warnings += 1
                    elif tracker.status == SLAStatus.CRITICAL:
                        critical += 1
                    elif tracker.status == SLAStatus.BREACHED:
                        breaches += 1

            logger.info(
                f"✅ SLA check complete: {checked} tickets checked, "
                f"{warnings} warnings, {critical} critical, {breaches} breaches"
            )

            return {
                "checked": checked,
                "warnings": warnings,
                "critical": critical,
                "breaches": breaches
            }

        except Exception as e:
            logger.error(f"❌ SLA check failed: {e}")
            return {"error": str(e)}
