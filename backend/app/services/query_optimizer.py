#!/usr/bin/env python3
"""
Query Optimizer - Centralized optimized database queries
"""

from typing import List, Optional
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from loguru import logger

from app.models.ticket import TicketHistory, TicketStatus
from app.models.team import TeamMember, Skill
from app.models.sla import SLATracker, SLAStatus
from app.core.database import get_redis
import json


class QueryOptimizer:
    """Provides optimized database queries with eager loading and caching"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
        self.cache_ttl = 300  # 5 minutes

    def get_active_tickets_with_relations(
        self,
        status_list: List[TicketStatus] = None
    ) -> List[TicketHistory]:
        """
        Get active tickets with all relationships eagerly loaded
        Prevents N+1 query problems
        """
        if status_list is None:
            status_list = [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS]

        query = self.db.query(TicketHistory).options(
            joinedload(TicketHistory.assigned_to).selectinload(TeamMember.skills),
            joinedload(TicketHistory.sla_tracker),
            selectinload(TicketHistory.escalations),
            selectinload(TicketHistory.collaborations)
        ).filter(
            TicketHistory.status.in_(status_list)
        )

        return query.all()

    def get_team_members_with_workload(
        self,
        team_level: Optional[str] = None,
        active_only: bool = True
    ) -> List[dict]:
        """
        Get team members with their current workload (cached)
        Single optimized query
        """
        cache_key = f"query:team_workload:{team_level}:{active_only}"

        # Try cache first
        cached = self.redis.get(cache_key)
        if cached:
            logger.debug(f"✅ Cache hit: {cache_key}")
            return json.loads(cached)

        # Build query
        query = self.db.query(
            TeamMember,
            func.count(TicketHistory.id).label('current_tickets')
        ).outerjoin(
            TicketHistory,
            and_(
                TicketHistory.assigned_to_id == TeamMember.id,
                TicketHistory.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
            )
        )

        if active_only:
            query = query.filter(TeamMember.active == True)

        if team_level:
            query = query.filter(TeamMember.team_level == team_level)

        query = query.group_by(TeamMember.id)

        results = []
        for member, ticket_count in query.all():
            results.append({
                "id": member.id,
                "name": member.name,
                "email": member.email,
                "team_level": member.team_level,
                "current_tickets": ticket_count,
                "max_tickets": member.max_tickets,
                "utilization": round((ticket_count / member.max_tickets * 100) if member.max_tickets > 0 else 0, 1),
                "available_capacity": max(0, member.max_tickets - ticket_count)
            })

        # Cache result
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(results))

        return results

    def get_sla_at_risk_optimized(self) -> List[dict]:
        """
        Get all at-risk tickets with optimized joins
        """
        cache_key = "query:sla_at_risk"

        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Single query with all joins
        results = self.db.query(
            SLATracker,
            TicketHistory,
            TeamMember
        ).join(
            TicketHistory,
            SLATracker.ticket_id == TicketHistory.id
        ).outerjoin(
            TeamMember,
            TicketHistory.assigned_to_id == TeamMember.id
        ).filter(
            SLATracker.status.in_([SLAStatus.AT_RISK, SLAStatus.CRITICAL]),
            SLATracker.paused == False
        ).all()

        at_risk_tickets = []
        for tracker, ticket, member in results:
            at_risk_tickets.append({
                "ticket_id": ticket.redmine_ticket_id,
                "subject": ticket.subject,
                "priority": ticket.priority.value,
                "sla_status": tracker.status.value,
                "remaining_minutes": tracker.calculate_time_remaining("resolution"),
                "assigned_to": member.name if member else None,
                "completion_percentage": tracker.get_completion_percentage("resolution")
            })

        # Cache for 1 minute (frequently changing)
        self.redis.setex(cache_key, 60, json.dumps(at_risk_tickets))

        return at_risk_tickets

    def get_historical_tickets_for_training(
        self,
        days_back: int = 90,
        limit: int = 10000
    ) -> List[TicketHistory]:
        """
        Get resolved tickets for ML training with minimal data
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Only select needed columns for training
        tickets = self.db.query(TicketHistory).filter(
            TicketHistory.resolved_at.isnot(None),
            TicketHistory.created_at >= cutoff_date,
            TicketHistory.category.isnot(None),
            TicketHistory.complexity.isnot(None)
        ).limit(limit).all()

        return tickets

    def get_daily_ticket_volumes(
        self,
        days_back: int = 90
    ) -> List[tuple]:
        """
        Get daily ticket volumes for forecasting
        Optimized aggregation query
        """
        cache_key = f"query:daily_volumes:{days_back}"

        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        cutoff_date = datetime.now() - timedelta(days=days_back)

        results = self.db.query(
            func.date(TicketHistory.created_at).label('date'),
            func.count(TicketHistory.id).label('count')
        ).filter(
            TicketHistory.created_at >= cutoff_date
        ).group_by(
            func.date(TicketHistory.created_at)
        ).order_by(
            func.date(TicketHistory.created_at)
        ).all()

        # Convert to serializable format
        volumes = [(str(row[0]), row[1]) for row in results]

        # Cache for 1 hour
        self.redis.setex(cache_key, 3600, json.dumps(volumes))

        return volumes

    def get_team_performance_stats(
        self,
        days_back: int = 30
    ) -> List[dict]:
        """
        Get team performance statistics with optimized aggregation
        """
        cache_key = f"query:team_performance:{days_back}"

        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        cutoff_date = datetime.now() - timedelta(days=days_back)

        # Single aggregation query
        results = self.db.query(
            TeamMember.id,
            TeamMember.name,
            TeamMember.team_level,
            func.count(TicketHistory.id).label('tickets_resolved'),
            func.avg(TicketHistory.actual_resolution_hours).label('avg_resolution_hours'),
            func.sum(
                func.case(
                    (TicketHistory.sla_breached == False, 1),
                    else_=0
                )
            ).label('sla_met'),
            func.count(TicketHistory.id).label('total_tickets')
        ).join(
            TicketHistory,
            TicketHistory.assigned_to_id == TeamMember.id
        ).filter(
            TicketHistory.resolved_at.isnot(None),
            TicketHistory.resolved_at >= cutoff_date
        ).group_by(
            TeamMember.id,
            TeamMember.name,
            TeamMember.team_level
        ).all()

        performance = []
        for row in results:
            sla_compliance = (row.sla_met / row.total_tickets * 100) if row.total_tickets > 0 else 0

            performance.append({
                "member_id": row.id,
                "name": row.name,
                "team_level": row.team_level,
                "tickets_resolved": row.tickets_resolved,
                "avg_resolution_hours": round(float(row.avg_resolution_hours or 0), 2),
                "sla_compliance_rate": round(sla_compliance, 1),
                "sla_breaches": row.total_tickets - row.sla_met
            })

        # Cache for 30 minutes
        self.redis.setex(cache_key, 1800, json.dumps(performance))

        return performance

    def invalidate_cache(self, pattern: str = None):
        """
        Invalidate cached queries

        Args:
            pattern: Redis key pattern to invalidate (e.g., "query:team_*")
                    If None, invalidates all query caches
        """
        try:
            if pattern is None:
                pattern = "query:*"

            # Get all matching keys
            keys = []
            for key in self.redis.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                self.redis.delete(*keys)
                logger.info(f"✅ Invalidated {len(keys)} cached queries")

        except Exception as e:
            logger.error(f"❌ Cache invalidation failed: {e}")

    def get_cache_stats(self) -> dict:
        """Get query cache statistics"""
        try:
            query_keys = list(self.redis.scan_iter(match="query:*"))
            total_size = sum(
                len(self.redis.get(key) or b'')
                for key in query_keys
            )

            return {
                "cached_queries": len(query_keys),
                "total_size_bytes": total_size,
                "total_size_kb": round(total_size / 1024, 2)
            }
        except Exception as e:
            logger.error(f"❌ Cache stats failed: {e}")
            return {"error": str(e)}
