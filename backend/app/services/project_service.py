#!/usr/bin/env python3
"""
Project analytics service.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_redis
from app.models.ticket import TicketHistory, TicketStatus, TicketPriority
from app.models.team import TeamMember
from app.schemas.project import (
    ProjectDetail,
    ProjectPriorityBreakdown,
    ProjectTrendPoint,
    ProjectRecentTicket,
    ProjectStatusBreakdown,
    ProjectSummary,
    ProjectTeamContributor,
)
from app.services.llm_service import EnhancedLLMService

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import BackgroundTasks

AI_INSIGHT_CACHE_TTL_SECONDS = 60 * 60  # 1 hour cache
AI_INSIGHT_INFLIGHT_TTL_SECONDS = 5 * 60  # prevent duplicate generation for 5 minutes


class ProjectAnalyticsService:
    """Aggregate project-level metrics derived from ticket history."""

    OPEN_STATUSES = {
        TicketStatus.NEW,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.PENDING,
        TicketStatus.REOPENED,
    }
    RESOLVED_STATUSES = {TicketStatus.RESOLVED, TicketStatus.CLOSED}

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_project_summaries(self) -> List[ProjectSummary]:
        """Return aggregate metrics per Jira project."""

        base_query = (
            self.db.query(
                TicketHistory.project_jira_id.label("project_jira_id"),
                func.count(TicketHistory.id).label("total_tickets"),
                func.sum(
                    case(
                        (
                            TicketHistory.status.in_([status.value for status in self.OPEN_STATUSES]),
                            1,
                        ),
                        else_=0,
                    )
                ).label("open_tickets"),
                func.sum(
                    case(
                        (
                            TicketHistory.status.in_([status.value for status in self.RESOLVED_STATUSES]),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolved_tickets"),
                func.sum(
                    case(
                        (
                            TicketHistory.sla_breached.is_(True),
                            1,
                        ),
                        else_=0,
                    )
                ).label("breached_tickets"),
                func.count(func.distinct(TicketHistory.assigned_to_id)).label("active_engineers"),
                func.max(
                    func.coalesce(
                        TicketHistory.updated_at,
                        TicketHistory.resolved_at,
                        TicketHistory.created_at,
                    )
                ).label("last_activity"),
                func.sum(
                    case(
                        (
                            and_(
                                TicketHistory.resolved_at.isnot(None),
                                TicketHistory.sla_breached.is_(False),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolved_on_time"),
            )
            .filter(TicketHistory.project_jira_id.isnot(None))
            .group_by(TicketHistory.project_jira_id)
        )

        summaries: List[ProjectSummary] = []

        for row in base_query:
            resolved_tickets = row.resolved_tickets or 0
            resolved_on_time = row.resolved_on_time or 0

            compliance_rate = (
                (resolved_on_time / resolved_tickets) * 100 if resolved_tickets else 100.0
            )

            summaries.append(
                ProjectSummary(
                    project_jira_id=row.project_jira_id,
                    total_tickets=row.total_tickets or 0,
                    open_tickets=row.open_tickets or 0,
                    resolved_tickets=resolved_tickets,
                    breached_tickets=row.breached_tickets or 0,
                    sla_compliance_rate=round(compliance_rate, 2),
                    active_engineers=row.active_engineers or 0,
                    last_activity=row.last_activity,
                )
            )

        summaries.sort(
            key=lambda item: item.last_activity or datetime.min,
            reverse=True,
        )

        return summaries

    def get_project_detail(self, project_jira_id: str) -> Optional[ProjectDetail]:
        """Return deep metrics for a single project."""

        summaries = {
            summary.project_jira_id: summary
            for summary in self.get_project_summaries()
        }

        summary = summaries.get(project_jira_id)
        if not summary:
            return None

        status_breakdown = self._status_breakdown(project_jira_id)
        priority_breakdown = self._priority_breakdown(project_jira_id)
        contributors = self._team_contributors(project_jira_id)
        recent_tickets = self._recent_tickets(project_jira_id)
        trend = self._trend_data(project_jira_id)
        cached_insight = _get_cached_ai_insight(summary.project_jira_id)

        return ProjectDetail(
            summary=summary,
            status_breakdown=status_breakdown,
            priority_breakdown=priority_breakdown,
            team_contributors=contributors,
            recent_tickets=recent_tickets,
            trend=trend,
            ai_insights=cached_insight,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _status_breakdown(self, project_jira_id: str) -> List[ProjectStatusBreakdown]:
        rows = (
            self.db.query(
                TicketHistory.status,
                func.count(TicketHistory.id).label("count"),
            )
            .filter(TicketHistory.project_jira_id == project_jira_id)
            .group_by(TicketHistory.status)
            .all()
        )

        return [
            ProjectStatusBreakdown(status=row.status, count=row.count or 0)
            for row in rows
        ]

    def _priority_breakdown(self, project_jira_id: str) -> List[ProjectPriorityBreakdown]:
        rows = (
            self.db.query(
                TicketHistory.priority,
                func.count(TicketHistory.id).label("count"),
            )
            .filter(TicketHistory.project_jira_id == project_jira_id)
            .group_by(TicketHistory.priority)
            .all()
        )

        return [
            ProjectPriorityBreakdown(priority=row.priority, count=row.count or 0)
            for row in rows
        ]

    def _team_contributors(self, project_jira_id: str) -> List[ProjectTeamContributor]:
        rows = (
            self.db.query(
                TeamMember.id.label("member_id"),
                TeamMember.name,
                TeamMember.email,
                func.count(TicketHistory.id).label("total_tickets"),
                func.sum(
                    case(
                        (
                            TicketHistory.status.in_(
                                [status.value for status in self.RESOLVED_STATUSES]
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolved_tickets"),
                func.sum(
                    case(
                        (
                            and_(
                                TicketHistory.status.in_(
                                    [status.value for status in self.RESOLVED_STATUSES]
                                ),
                                TicketHistory.sla_breached.is_(False),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("resolved_on_time"),
            )
            .join(TeamMember, TicketHistory.assigned_to_id == TeamMember.id)
            .filter(TicketHistory.project_jira_id == project_jira_id)
            .group_by(TeamMember.id, TeamMember.name, TeamMember.email)
            .order_by(func.count(TicketHistory.id).desc())
            .all()
        )

        contributors: List[ProjectTeamContributor] = []

        for row in rows:
            resolved = row.resolved_tickets or 0
            on_time = row.resolved_on_time or 0
            compliance = (on_time / resolved) * 100 if resolved else 0.0

            contributors.append(
                ProjectTeamContributor(
                    member_id=row.member_id,
                    name=row.name,
                    email=row.email,
                    total_tickets=row.total_tickets or 0,
                    resolved_tickets=resolved,
                    sla_compliance_rate=round(compliance, 2),
                )
            )

        return contributors

    def _recent_tickets(self, project_jira_id: str) -> List[ProjectRecentTicket]:
        rows = (
            self.db.query(
                TicketHistory.id,
                TicketHistory.redmine_ticket_id,
                TicketHistory.subject,
                TicketHistory.status,
                TicketHistory.priority,
                TicketHistory.sla_breached,
                TicketHistory.created_at,
                TicketHistory.resolved_at,
                TeamMember.name.label("assignee_name"),
            )
            .outerjoin(TeamMember, TicketHistory.assigned_to_id == TeamMember.id)
            .filter(TicketHistory.project_jira_id == project_jira_id)
            .order_by(TicketHistory.updated_at.desc().nullslast(), TicketHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            ProjectRecentTicket(
                ticket_id=row.id,
                redmine_ticket_id=row.redmine_ticket_id,
                subject=row.subject or "",
                status=row.status,
                priority=row.priority,
                assigned_to=row.assignee_name,
                sla_breached=bool(row.sla_breached),
                created_at=row.created_at,
                resolved_at=row.resolved_at,
            )
            for row in rows
        ]

    def _trend_data(self, project_jira_id: str, days: int = 30) -> List[ProjectTrendPoint]:
        end_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days - 1)

        created_rows = (
            self.db.query(
                func.date_trunc('day', TicketHistory.created_at).label('day'),
                func.count(TicketHistory.id).label('count'),
            )
            .filter(
                TicketHistory.project_jira_id == project_jira_id,
                TicketHistory.created_at.isnot(None),
                TicketHistory.created_at >= start_date,
            )
            .group_by(func.date_trunc('day', TicketHistory.created_at))
            .all()
        )

        resolved_rows = (
            self.db.query(
                func.date_trunc('day', TicketHistory.resolved_at).label('day'),
                func.count(TicketHistory.id).label('resolved'),
                func.sum(
                    case((TicketHistory.sla_breached.is_(True), 1), else_=0)
                ).label('breached'),
                func.sum(
                    case((TicketHistory.sla_breached.is_(False), 1), else_=0)
                ).label('on_time'),
            )
            .filter(
                TicketHistory.project_jira_id == project_jira_id,
                TicketHistory.resolved_at.isnot(None),
                TicketHistory.resolved_at >= start_date,
            )
            .group_by(func.date_trunc('day', TicketHistory.resolved_at))
            .all()
        )

        created_map = {
            row.day.date(): row.count or 0 for row in created_rows
        }
        resolved_map = {
            row.day.date(): {
                "resolved": row.resolved or 0,
                "breached": row.breached or 0,
                "on_time": row.on_time or 0,
            }
            for row in resolved_rows
        }

        trend: List[ProjectTrendPoint] = []

        for day_offset in range(days):
            day = (start_date + timedelta(days=day_offset)).date()
            resolved_stats = resolved_map.get(day, {"resolved": 0, "breached": 0, "on_time": 0})
            resolved = resolved_stats["resolved"]
            on_time = resolved_stats["on_time"]
            compliance = (on_time / resolved * 100) if resolved else 100.0

            trend.append(
                ProjectTrendPoint(
                    date=datetime.combine(day, datetime.min.time()),
                    created=created_map.get(day, 0),
                    resolved=resolved,
                    breached=resolved_stats["breached"],
                    sla_compliance_rate=round(compliance, 2),
                )
            )

        return trend


def _cache_key(project_id: str) -> str:
    return f"project:ai_insights:{project_id}"


def _inflight_key(project_id: str) -> str:
    return f"project:ai_insights:inflight:{project_id}"


def _get_cached_ai_insight(project_id: str) -> Optional[str]:
    try:
        cached = get_redis().get(_cache_key(project_id))
        if not cached:
            return None
        if isinstance(cached, bytes):
            return cached.decode("utf-8")
        return str(cached)
    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight cache read failed: %s", exc)
        return None


def _set_cached_ai_insight(project_id: str, insight: str) -> None:
    if not insight:
        return

    try:
        get_redis().setex(
            _cache_key(project_id),
            AI_INSIGHT_CACHE_TTL_SECONDS,
            insight,
        )
        logger.info("💾 Cached AI insight for project %s", project_id)
    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight cache write failed: %s", exc)


def _mark_insight_inflight(project_id: str) -> bool:
    try:
        acquired = bool(
            get_redis().set(
                _inflight_key(project_id),
                "1",
                nx=True,
                ex=AI_INSIGHT_INFLIGHT_TTL_SECONDS,
            )
        )
        if acquired:
            logger.info("🧠 Scheduling AI insight generation for project %s", project_id)
        return acquired
    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight inflight flag failed: %s", exc)
        return False


def _clear_insight_inflight(project_id: str) -> None:
    try:
        get_redis().delete(_inflight_key(project_id))
    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight inflight cleanup failed: %s", exc)


def _build_ai_prompt(
    summary: ProjectSummary,
    status_breakdown: List[ProjectStatusBreakdown],
    priority_breakdown: List[ProjectPriorityBreakdown],
    contributors: List[ProjectTeamContributor],
    recent_tickets: List[ProjectRecentTicket],
) -> str:
    status_lines = ", ".join(
        f"{item.status}: {item.count}" for item in status_breakdown
    ) or "No status data"
    priority_lines = ", ".join(
        f"{item.priority}: {item.count}" for item in priority_breakdown
    ) or "No priority data"
    top_engineers = ", ".join(
        f"{member.name} ({member.resolved_tickets} resolved)"
        for member in contributors[:5]
    ) or "No active contributors recorded"

    recent_snapshot = "\n".join(
        f"- #{ticket.redmine_ticket_id} {ticket.subject[:60]} "
        f"(status: {ticket.status}, SLA: {'breached' if ticket.sla_breached else 'ok'})"
        for ticket in recent_tickets[:5]
    ) or "- No recent ticket activity"

    return f"""
You are an SRE project analyst. Review the following operational metrics for Jira project {summary.project_jira_id} and provide:
1. A short health summary (1 paragraph).
2. Top 3 risks or hotspots as bullet points.
3. Recommended next actions for the engineering lead.

Metrics overview:
- Total tickets: {summary.total_tickets}
- Open tickets: {summary.open_tickets}
- Resolved tickets: {summary.resolved_tickets}
- SLA breaches: {summary.breached_tickets}
- SLA compliance rate: {summary.sla_compliance_rate:.2f}%
- Active engineers: {summary.active_engineers}

Status distribution: {status_lines}
Priority distribution: {priority_lines}
Top contributors: {top_engineers}
Recent ticket snapshot:
{recent_snapshot}

Focus on operational insights and keep output concise and executive-friendly.
"""


def _compute_ai_insight_text(
    db: Session,
    summary: ProjectSummary,
    status_breakdown: List[ProjectStatusBreakdown],
    priority_breakdown: List[ProjectPriorityBreakdown],
    contributors: List[ProjectTeamContributor],
    recent_tickets: List[ProjectRecentTicket],
) -> Optional[str]:
    try:
        llm_service = EnhancedLLMService(db)
        prompt = _build_ai_prompt(
            summary,
            status_breakdown,
            priority_breakdown,
            contributors,
            recent_tickets,
        )

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            insights = loop.run_until_complete(
                llm_service._call_llm_async(prompt.strip(), temperature=0.2)
            )
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

        cleaned = insights.strip() if insights else ""
        return cleaned or None

    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight generation failed: %s", exc)
        return None


def _generate_ai_insight_task(payload: Dict[str, Any]) -> None:
    project_id = payload.get("project_id")
    if not project_id:
        return

    db = SessionLocal()
    try:
        summary = ProjectSummary.model_validate(payload["summary"])
        status_breakdown = [
            ProjectStatusBreakdown.model_validate(item)
            for item in payload.get("status_breakdown", [])
        ]
        priority_breakdown = [
            ProjectPriorityBreakdown.model_validate(item)
            for item in payload.get("priority_breakdown", [])
        ]
        contributors = [
            ProjectTeamContributor.model_validate(item)
            for item in payload.get("team_contributors", [])
        ]
        recent_tickets = [
            ProjectRecentTicket.model_validate(item)
            for item in payload.get("recent_tickets", [])
        ]

        insight = _compute_ai_insight_text(
            db,
            summary,
            status_breakdown,
            priority_breakdown,
            contributors,
            recent_tickets,
        )

        if insight:
            _set_cached_ai_insight(project_id, insight)
            logger.info("🤖 Generated AI insight for project %s", project_id)
        else:
            logger.info("⚠️ AI insight generation returned empty output for project %s", project_id)

    except Exception as exc:  # pragma: no cover
        logger.warning("AI insight background task failed: %s", exc)
    finally:
        _clear_insight_inflight(project_id)
        db.close()


def schedule_ai_insight_generation(
    detail: ProjectDetail,
    background_tasks: "BackgroundTasks",
) -> None:
    if background_tasks is None:
        return

    project_id = detail.summary.project_jira_id
    if not project_id:
        return

    if _get_cached_ai_insight(project_id):
        return

    if not _mark_insight_inflight(project_id):
        return

    payload = {
        "project_id": project_id,
        "summary": detail.summary.model_dump(mode="json"),
        "status_breakdown": [
            item.model_dump(mode="json") for item in detail.status_breakdown
        ],
        "priority_breakdown": [
            item.model_dump(mode="json") for item in detail.priority_breakdown
        ],
        "team_contributors": [
            item.model_dump(mode="json") for item in detail.team_contributors
        ],
        "recent_tickets": [
            item.model_dump(mode="json") for item in detail.recent_tickets
        ],
    }

    background_tasks.add_task(_generate_ai_insight_task, payload)
