#!/usr/bin/env python3
"""
Workload Manager - Real-time capacity tracking and load balancing
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.team import TeamMember, TeamLevel
from app.models.ticket import TicketHistory, TicketStatus
from app.core.database import get_redis
from app.services.scheduling_service import SchedulingService


class WorkloadManager:
    """Manages team workload and capacity"""

    def __init__(self, db: Session):
        self.db = db
        self.redis = get_redis()
        self.scheduling = SchedulingService(db)

    def get_current_workload(self, user_id: int, use_cache: bool = True) -> int:
        """
        Get current workload for a user (In Progress tickets only)

        Args:
            user_id: User ID
            use_cache: Whether to use Redis cache

        Returns:
            Number of active tickets
        """
        try:
            # Try cache first
            if use_cache:
                cached = self.redis.get(f"workload:user:{user_id}")
                if cached:
                    return int(cached)

            # Query database
            workload = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == user_id,
                TicketHistory.status.in_([
                    TicketStatus.ASSIGNED,
                    TicketStatus.IN_PROGRESS
                ])
            ).count()

            # Cache result
            self.redis.setex(f"workload:user:{user_id}", 300, workload)  # 5 min TTL

            return workload

        except Exception as e:
            logger.error(f"❌ Error getting workload for user {user_id}: {e}")
            return 0

    def get_team_workload(self, team_level: str = None) -> List[Dict]:
        """
        Get workload for entire team or specific level

        Returns:
            List of {user_id, name, current_tickets, max_tickets, utilization, status}
        """
        try:
            query = self.db.query(TeamMember).filter(TeamMember.active == True)

            if team_level:
                query = query.filter(TeamMember.team_level == TeamLevel(team_level))

            members = query.all()
            workload_data = []

            for member in members:
                current_tickets = self.get_current_workload(member.id)
                max_tickets = member.max_tickets

                utilization = (current_tickets / max_tickets * 100) if max_tickets > 0 else 0

                if current_tickets >= max_tickets:
                    status = "at_capacity"
                elif current_tickets >= max_tickets * 0.8:
                    status = "high_load"
                elif current_tickets >= max_tickets * 0.5:
                    status = "moderate_load"
                else:
                    status = "available"

                workload_data.append({
                    "user_id": member.id,
                    "redmine_user_id": member.redmine_user_id,
                    "name": member.name,
                    "email": member.email,
                    "team_level": member.team_level,
                    "current_tickets": current_tickets,
                    "max_tickets": max_tickets,
                    "utilization": round(utilization, 1),
                    "status": status,
                    "is_available": self.scheduling.is_member_available(member)
                })

            # Sort by utilization
            workload_data.sort(key=lambda x: x['utilization'])

            return workload_data

        except Exception as e:
            logger.error(f"❌ Error getting team workload: {e}")
            return []

    def get_available_members(
        self,
        team_level: str,
        min_capacity: int = 1
    ) -> List[TeamMember]:
        """
        Get available team members with capacity

        Args:
            team_level: L1, L2, or L3
            min_capacity: Minimum available capacity required

        Returns:
            List of available TeamMember objects
        """
        try:
            members = self.db.query(TeamMember).filter(
                TeamMember.team_level == TeamLevel(team_level),
                TeamMember.active == True
            ).all()

            available = []
            for member in members:
                # Check availability based on shifts / leave
                if not self.scheduling.is_member_available(member):
                    continue

                # Check capacity
                current_workload = self.get_current_workload(member.id)
                available_capacity = member.max_tickets - current_workload

                if available_capacity >= min_capacity:
                    available.append(member)

            logger.info(f"Found {len(available)} available {team_level} members")
            return available

        except Exception as e:
            logger.error(f"❌ Error getting available members: {e}")
            return []

    def update_workload_cache(self, user_id: int):
        """Force update workload cache"""
        try:
            workload = self.get_current_workload(user_id, use_cache=False)
            logger.debug(f"Updated workload cache for user {user_id}: {workload} tickets")
            return workload
        except Exception as e:
            logger.error(f"❌ Error updating workload cache: {e}")
            return 0

    def increment_workload(self, user_id: int):
        """Increment workload counter (when ticket assigned)"""
        if not self.redis:
            logger.debug("Redis not available, skipping workload increment")
            return

        try:
            # Get fresh count from database to ensure accuracy
            current = self.get_current_workload(user_id, use_cache=False)
            # Cache for 15 minutes (improved from 5 minutes)
            self.redis.setex(f"workload:user:{user_id}", 900, current)
            logger.debug(f"Updated workload cache for user {user_id}: {current} tickets")
        except Exception as e:
            logger.warning(f"⚠️ Error updating workload cache: {e}")

    def decrement_workload(self, user_id: int):
        """Decrement workload counter (when ticket resolved)"""
        if not self.redis:
            logger.debug("Redis not available, skipping workload decrement")
            return

        try:
            # Get fresh count from database to ensure accuracy
            current = self.get_current_workload(user_id, use_cache=False)
            # Cache for 15 minutes (improved from 5 minutes)
            self.redis.setex(f"workload:user:{user_id}", 900, current)
            logger.debug(f"Updated workload cache for user {user_id}: {current} tickets")
        except Exception as e:
            logger.warning(f"⚠️ Error updating workload cache: {e}")

    def get_capacity_summary(self) -> Dict:
        """Get overall team capacity summary"""
        try:
            l1_workload = self.get_team_workload("L1")
            l2_workload = self.get_team_workload("L2")
            l3_workload = self.get_team_workload("L3")

            def calculate_stats(workload_data):
                if not workload_data:
                    return {"available": 0, "at_capacity": 0, "total_capacity": 0, "used_capacity": 0}

                available = sum(1 for w in workload_data if w['status'] == 'available')
                at_capacity = sum(1 for w in workload_data if w['status'] == 'at_capacity')
                total_capacity = sum(w['max_tickets'] for w in workload_data)
                used_capacity = sum(w['current_tickets'] for w in workload_data)

                return {
                    "members": len(workload_data),
                    "available": available,
                    "at_capacity": at_capacity,
                    "total_capacity": total_capacity,
                    "used_capacity": used_capacity,
                    "utilization": round(used_capacity / total_capacity * 100, 1) if total_capacity > 0 else 0
                }

            return {
                "l1": calculate_stats(l1_workload),
                "l2": calculate_stats(l2_workload),
                "l3": calculate_stats(l3_workload),
                "overall": {
                    "total_members": len(l1_workload) + len(l2_workload) + len(l3_workload),
                    "total_capacity": (
                        calculate_stats(l1_workload)['total_capacity'] +
                        calculate_stats(l2_workload)['total_capacity'] +
                        calculate_stats(l3_workload)['total_capacity']
                    ),
                    "total_used": (
                        calculate_stats(l1_workload)['used_capacity'] +
                        calculate_stats(l2_workload)['used_capacity'] +
                        calculate_stats(l3_workload)['used_capacity']
                    )
                }
            }

        except Exception as e:
            logger.error(f"❌ Error getting capacity summary: {e}")
            return {}

    def suggest_rebalancing(self) -> List[Dict]:
        """
        Suggest workload rebalancing actions

        Returns:
            List of suggested reassignments
        """
        try:
            suggestions = []

            for level in ["L1", "L2", "L3"]:
                workload = self.get_team_workload(level)

                if len(workload) < 2:
                    continue

                # Find overloaded and underloaded members
                overloaded = [w for w in workload if w['utilization'] >= 90]
                underloaded = [w for w in workload if w['utilization'] <= 50]

                for overloaded_member in overloaded:
                    for underloaded_member in underloaded:
                        # Get tickets to reassign
                        tickets_to_move = self.db.query(TicketHistory).filter(
                            TicketHistory.assigned_to_id == overloaded_member['user_id'],
                            TicketHistory.status == TicketStatus.ASSIGNED
                        ).limit(2).all()

                        for ticket in tickets_to_move:
                            suggestions.append({
                                "action": "reassign",
                                "ticket_id": ticket.redmine_ticket_id,
                                "from_user": overloaded_member['name'],
                                "to_user": underloaded_member['name'],
                                "reason": f"Balance workload ({overloaded_member['utilization']:.0f}% → {underloaded_member['utilization']:.0f}%)"
                            })

            return suggestions

        except Exception as e:
            logger.error(f"❌ Error suggesting rebalancing: {e}")
            return []

    def check_capacity_alerts(self) -> List[Dict]:
        """
        Check for capacity-related alerts

        Returns:
            List of alerts
        """
        try:
            alerts = []
            capacity = self.get_capacity_summary()

            # Check L1 capacity
            if capacity['l1']['utilization'] >= 90:
                alerts.append({
                    "level": "critical",
                    "team": "L1",
                    "message": f"L1 team at {capacity['l1']['utilization']}% capacity",
                    "action": "Consider escalating new tickets to L2"
                })
            elif capacity['l1']['utilization'] >= 75:
                alerts.append({
                    "level": "warning",
                    "team": "L1",
                    "message": f"L1 team at {capacity['l1']['utilization']}% capacity",
                    "action": "Monitor closely"
                })

            # Check overall capacity
            overall_util = (
                capacity['overall']['total_used'] /
                capacity['overall']['total_capacity'] * 100
                if capacity['overall']['total_capacity'] > 0 else 0
            )

            if overall_util >= 85:
                alerts.append({
                    "level": "critical",
                    "team": "All",
                    "message": f"Overall team at {overall_util:.1f}% capacity",
                    "action": "Consider adding resources or prioritizing tickets"
                })

            return alerts

        except Exception as e:
            logger.error(f"❌ Error checking capacity alerts: {e}")
            return []

    def get_user_ticket_distribution(self, user_id: int) -> Dict:
        """Get detailed ticket distribution for a user"""
        try:
            tickets = self.db.query(TicketHistory).filter(
                TicketHistory.assigned_to_id == user_id,
                TicketHistory.status.in_([
                    TicketStatus.ASSIGNED,
                    TicketStatus.IN_PROGRESS
                ])
            ).all()

            by_priority = {}
            by_category = {}
            by_status = {}

            for ticket in tickets:
                # By priority
                priority = ticket.priority.value
                by_priority[priority] = by_priority.get(priority, 0) + 1

                # By category
                category = ticket.category.value if ticket.category else "uncategorized"
                by_category[category] = by_category.get(category, 0) + 1

                # By status
                status = ticket.status.value
                by_status[status] = by_status.get(status, 0) + 1

            return {
                "total_tickets": len(tickets),
                "by_priority": by_priority,
                "by_category": by_category,
                "by_status": by_status
            }

        except Exception as e:
            logger.error(f"❌ Error getting ticket distribution: {e}")
            return {}
