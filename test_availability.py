#!/usr/bin/env python3
"""Test script to check member availability"""

import sys
sys.path.insert(0, '/app')

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.team import TeamMember
from app.services.scheduling_service import SchedulingService
from app.services.workload_manager import WorkloadManager
from datetime import datetime
import pytz

def test_availability():
    db = SessionLocal()
    try:
        scheduling = SchedulingService(db)
        workload_mgr = WorkloadManager(db, scheduling)

        # Get L1 team members
        l1_members = db.query(TeamMember).filter(
            TeamMember.team_level == "L1",
            TeamMember.active == True
        ).all()

        print(f"Found {len(l1_members)} active L1 members")
        print(f"Current time (UTC): {datetime.utcnow().replace(tzinfo=pytz.UTC)}")

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        for member in l1_members[:5]:  # Check first 5
            local_dt = scheduling._to_member_timezone(member, now)
            print(f"\n{'='*60}")
            print(f"Member: {member.name} (ID: {member.id})")
            print(f"  Local time: {local_dt}")
            print(f"  Day of week: {local_dt.weekday()} (0=Monday)")
            print(f"  Hour: {local_dt.hour}")

            # Check if on leave
            on_leave = scheduling.is_member_on_leave(member, local_dt.date())
            print(f"  On leave: {on_leave}")

            # Check shifts
            from app.models.schedule import ShiftAssignment
            from sqlalchemy import or_

            shifts = db.query(ShiftAssignment).filter(
                ShiftAssignment.team_member_id == member.id,
                ShiftAssignment.is_active.is_(True),
                or_(ShiftAssignment.effective_from.is_(None), ShiftAssignment.effective_from <= now.date()),
                or_(ShiftAssignment.effective_to.is_(None), ShiftAssignment.effective_to >= now.date()),
            ).all()

            print(f"  Active shifts count: {len(shifts)}")

            # Check today's shifts
            today_shifts = [s for s in shifts if s.day_of_week == local_dt.weekday()]
            print(f"  Today's shifts ({local_dt.weekday()}): {len(today_shifts)}")

            for shift in today_shifts:
                shift_start = shift.start_hour * 60 + shift.start_minute
                shift_end = shift.end_hour * 60 + shift.end_minute
                current_minutes = local_dt.hour * 60 + local_dt.minute

                print(f"    Shift: {shift.start_hour:02d}:{shift.start_minute:02d} - {shift.end_hour:02d}:{shift.end_minute:02d} (category: {shift.category})")
                print(f"    Current minutes: {current_minutes}, Shift: {shift_start}-{shift_end}")

                if shift_end < shift_start:  # Overnight shift
                    in_shift = current_minutes >= shift_start or current_minutes < shift_end
                    print(f"    Overnight shift, in_shift: {in_shift}")
                else:
                    in_shift = shift_start <= current_minutes < shift_end
                    print(f"    Normal shift, in_shift: {in_shift}")

            # Check if on active shift
            on_shift = scheduling.is_member_on_active_shift(member, now)
            print(f"  On active shift: {on_shift}")

            # Check workload
            workload = workload_mgr.get_current_workload(member.id)
            print(f"  Current workload: {workload}/{member.max_tickets}")

            # Overall availability
            available = scheduling.is_member_available(member, now)
            print(f"  >>> AVAILABLE: {available}")

        # Now check get_available_members
        print(f"\n{'='*60}")
        print("Testing get_available_members for L1:")
        available = workload_mgr.get_available_members("L1")
        print(f"Available L1 members: {len(available)}")
        for member in available:
            print(f"  - {member.name} (ID: {member.id})")

    finally:
        db.close()

if __name__ == "__main__":
    test_availability()
