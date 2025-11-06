#!/usr/bin/env python3
"""
Scheduling service - shift calendar and leave management helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Sequence, Tuple
import hashlib
import hmac
import random
from calendar import day_name

import pytz
from loguru import logger
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_

from app.models.team import TeamMember, TeamLevel
from app.models.schedule import (
    ShiftAssignment,
    MemberLeave,
    LeaveStatus,
    LeaveType,
    OnCallRotationEntry,
    OnCallAssignment,
    OnCallAssignmentStatus,
    OnCallRotationState,
)
from app.services.notification_service import NotificationService
from app.core.config import settings

# Treat these statuses as blocking availability
_BLOCKING_LEAVE_STATUSES = {
    LeaveStatus.APPROVED.value,
    LeaveStatus.PENDING.value,
}

_STANDARD_SHIFT_CATEGORY = "standard"
_ONCALL_SHIFT_CATEGORY = "oncall"
_ONCALL_TEAM_LEVELS = [TeamLevel.L1.value, TeamLevel.L2.value]


class SchedulingService:
    """Core scheduling utilities."""

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------- #
    # Shift helpers
    # --------------------------------------------------------------------- #
    def list_shift_assignments(
        self,
        team_level: Optional[str] = None,
        member_id: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[ShiftAssignment]:
        query = self.db.query(ShiftAssignment).options(joinedload(ShiftAssignment.team_member))

        if member_id:
            query = query.filter(ShiftAssignment.team_member_id == member_id)
        elif team_level:
            query = query.join(TeamMember).filter(TeamMember.team_level == TeamLevel(team_level))

        if not include_inactive:
            query = query.filter(ShiftAssignment.is_active.is_(True))

        return query.order_by(
            ShiftAssignment.team_member_id.asc(),
            ShiftAssignment.day_of_week.asc().nullsfirst(),
            ShiftAssignment.start_hour.asc(),
        ).all()

    def get_shift(self, shift_id: int) -> Optional[ShiftAssignment]:
        return (
            self.db.query(ShiftAssignment)
            .options(joinedload(ShiftAssignment.team_member))
            .filter(ShiftAssignment.id == shift_id)
            .first()
        )

    def create_shift(self, payload: Dict, created_by: str | None = None) -> ShiftAssignment:
        shift = ShiftAssignment()
        self._apply_shift_payload(shift, payload)

        if not shift.team_member:
            shift.team_member = self.db.query(TeamMember).filter(TeamMember.id == payload.get("team_member_id")).first()

        if not shift.team_member:
            raise ValueError("Team member not found")

        if not shift.team_level:
            shift.team_level = shift.team_member.team_level.value

        self.db.add(shift)
        self.db.commit()
        self.db.refresh(shift)

        logger.info(f"✅ Shift {shift.id} created by {created_by or 'system'} for member {shift.team_member_id}")
        return shift

    def update_shift(self, shift: ShiftAssignment, payload: Dict) -> ShiftAssignment:
        self._apply_shift_payload(shift, payload)
        self.db.commit()
        # Re-fetch to ensure relationships reflect latest state
        return self.get_shift(shift.id)

    def delete_shift(self, shift: ShiftAssignment):
        self.db.delete(shift)
        self.db.commit()

    def _apply_shift_payload(self, shift: ShiftAssignment, payload: Dict):
        """Validate and assign shift fields."""
        required_fields = ["team_member_id", "start_hour", "end_hour"]
        for field in required_fields:
            if getattr(shift, field, None) is None and payload.get(field) is None:
                raise ValueError(f"{field} is required")

        if "team_member_id" in payload:
            shift.team_member_id = int(payload["team_member_id"])

        if "team_level" in payload and payload["team_level"]:
            shift.team_level = payload["team_level"]
        elif shift.team_member:
            shift.team_level = shift.team_member.team_level.value

        for key in ["day_of_week", "start_hour", "start_minute", "end_hour", "end_minute", "priority"]:
            if key in payload and payload[key] is not None:
                value = int(payload[key])
                if key in {"start_hour", "end_hour"} and not (0 <= value <= 23):
                    raise ValueError("Hours must be between 0 and 23")
                if key in {"start_minute", "end_minute"} and not (0 <= value <= 59):
                    raise ValueError("Minutes must be between 0 and 59")
                if key == "day_of_week" and value not in range(0, 7):
                    raise ValueError("day_of_week must be between 0 (Mon) and 6 (Sun)")
                setattr(shift, key, value)

        if "timezone" in payload and payload["timezone"]:
            shift.timezone = payload["timezone"]

        if "category" in payload and payload["category"]:
            shift.category = payload["category"]

        if "effective_from" in payload:
            shift.effective_from = self._parse_date(payload.get("effective_from"))
        if "effective_to" in payload:
            shift.effective_to = self._parse_date(payload.get("effective_to"))

        if "generated_week_start" in payload:
            shift.generated_week_start = self._parse_date(payload.get("generated_week_start"))

        if "is_active" in payload and payload["is_active"] is not None:
            shift.is_active = bool(payload["is_active"])

        if "notes" in payload:
            shift.notes = payload.get("notes")

        if shift.start_minute is None:
            shift.start_minute = 0
        if shift.end_minute is None:
            shift.end_minute = 0
        if shift.priority is None:
            shift.priority = 50
        if shift.timezone in (None, ""):
            shift.timezone = "Asia/Kolkata"
        if shift.is_active is None:
            shift.is_active = True

        if not shift.category:
            shift.category = _STANDARD_SHIFT_CATEGORY

        # Basic check to ensure window makes sense (allow full-day coverage when start=end)
        start_total = shift.start_hour * 60 + shift.start_minute
        end_total = shift.end_hour * 60 + shift.end_minute
        if start_total == end_total:
            # Interpret as full-day coverage
            logger.debug(
                "Shift %s configured as full-day coverage (start=end=%s)",
                getattr(shift, "id", "<new>"),
                shift.start_hour,
            )

    # --------------------------------------------------------------------- #
    # Default shift utilities
    # --------------------------------------------------------------------- #
    def ensure_standard_weekday_shifts(self) -> int:
        """Ensure every active member has Mon-Fri 09:00-20:00 coverage."""

        members = (
            self.db.query(TeamMember)
            .filter(TeamMember.active.is_(True))
            .all()
        )

        created = 0
        for member in members:
            for day in range(0, 5):  # Monday-Friday
                exists = (
                    self.db.query(ShiftAssignment)
                    .filter(
                        ShiftAssignment.team_member_id == member.id,
                        ShiftAssignment.category == _STANDARD_SHIFT_CATEGORY,
                        ShiftAssignment.day_of_week == day,
                        ShiftAssignment.is_active.is_(True),
                    )
                    .first()
                )

                if exists:
                    continue

                shift = ShiftAssignment(
                    team_member_id=member.id,
                    team_level=member.team_level.value,
                    day_of_week=day,
                    start_hour=9,
                    start_minute=0,
                    end_hour=20,
                    end_minute=0,
                    timezone=member.timezone,
                    priority=50,
                    is_active=True,
                    category=_STANDARD_SHIFT_CATEGORY,
                )
                self.db.add(shift)
                created += 1

        if created:
            self.db.commit()
            logger.info("✅ Ensured %d standard shifts across team members", created)
        return created

    def _ensure_member_has_standard_shifts(self, member_id: int) -> int:
        """Ensure a specific member has active Mon-Fri standard shifts."""
        member = self.db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member or not member.active:
            return 0

        created = 0
        for day in range(0, 5):  # Monday-Friday
            shifts = (
                self.db.query(ShiftAssignment)
                .filter(
                    ShiftAssignment.team_member_id == member_id,
                    ShiftAssignment.category == _STANDARD_SHIFT_CATEGORY,
                    ShiftAssignment.day_of_week == day,
                )
                .all()
            )

            if len(shifts) > 1:
                # Duplicates found - delete all except the first one
                logger.warning(f"⚠️ Found {len(shifts)} duplicate standard shifts for member {member_id}, day {day}. Cleaning up...")
                keep_shift = shifts[0]
                for dup_shift in shifts[1:]:
                    logger.info(f"🗑️ Deleting duplicate shift ID {dup_shift.id} for member {member_id}, day {day}")
                    self.db.delete(dup_shift)
                # Ensure the kept shift is active
                if not keep_shift.is_active:
                    keep_shift.is_active = True
                    logger.info(f"✅ Reactivated standard shift for member {member_id}, day {day}")
            elif len(shifts) == 1:
                # Shift exists, ensure it's active
                if not shifts[0].is_active:
                    shifts[0].is_active = True
                    logger.info(f"✅ Reactivated standard shift for member {member_id}, day {day}")
            else:
                # Shift doesn't exist, create it
                shift = ShiftAssignment(
                    team_member_id=member_id,
                    team_level=member.team_level.value,
                    day_of_week=day,
                    start_hour=9,
                    start_minute=0,
                    end_hour=20,
                    end_minute=0,
                    timezone=member.timezone,
                    priority=50,
                    is_active=True,
                    category=_STANDARD_SHIFT_CATEGORY,
                )
                self.db.add(shift)
                created += 1
                logger.info(f"✅ Created standard shift for member {member_id}, day {day}")

        return created

    # --------------------------------------------------------------------- #
    # Leave helpers
    # --------------------------------------------------------------------- #
    def list_leaves(
        self,
        team_level: Optional[str] = None,
        status: Optional[str] = None,
        member_id: Optional[int] = None,
        include_past: bool = False,
    ) -> List[MemberLeave]:
        query = self.db.query(MemberLeave).options(joinedload(MemberLeave.team_member))

        if member_id:
            query = query.filter(MemberLeave.team_member_id == member_id)
        elif team_level:
            query = query.join(TeamMember).filter(TeamMember.team_level == TeamLevel(team_level))

        if status:
            query = query.filter(MemberLeave.status == status)

        if not include_past:
            today = date.today()
            query = query.filter(MemberLeave.end_date >= today)

        return query.order_by(MemberLeave.start_date.asc()).all()

    def get_leave(self, leave_id: int) -> Optional[MemberLeave]:
        return (
            self.db.query(MemberLeave)
            .options(joinedload(MemberLeave.team_member))
            .filter(MemberLeave.id == leave_id)
            .first()
        )

    def create_leave(
        self,
        member: TeamMember,
        payload: Dict,
        created_by: str,
        auto_approve: bool = True,
    ) -> MemberLeave:
        leave = MemberLeave()
        leave.team_member_id = member.id
        requested_status = payload.get("status")
        if auto_approve:
            leave.status = requested_status or LeaveStatus.APPROVED.value
        else:
            leave.status = requested_status or LeaveStatus.PENDING.value

        self._apply_leave_payload(leave, payload, require_dates=True)
        leave.created_by = created_by

        if auto_approve and leave.status == LeaveStatus.APPROVED.value:
            leave.approved_by = created_by
            leave.approved_at = datetime.utcnow()

        self.db.add(leave)
        self.db.commit()
        self.db.refresh(leave)
        logger.info(f"✅ Leave {leave.id} created for member {member.id} by {created_by}")
        return leave

    def update_leave(self, leave: MemberLeave, payload: Dict) -> MemberLeave:
        self._apply_leave_payload(leave, payload, require_dates=False)
        self.db.commit()
        self.db.refresh(leave)
        return leave

    def delete_leave(self, leave: MemberLeave) -> None:
        """Delete a leave entry."""
        self.db.delete(leave)
        self.db.commit()

    def set_leave_status(self, leave: MemberLeave, status: LeaveStatus, approved_by: str):
        leave.status = status.value
        if status == LeaveStatus.APPROVED:
            leave.approved_by = approved_by
            leave.approved_at = datetime.utcnow()
        elif status in {LeaveStatus.REJECTED, LeaveStatus.CANCELLED}:
            leave.approved_by = approved_by
            leave.approved_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(leave)

    def _apply_leave_payload(self, leave: MemberLeave, payload: Dict, require_dates: bool = False):
        start_raw = payload.get("start_date")
        end_raw = payload.get("end_date")

        start = self._parse_date(start_raw) if start_raw is not None else leave.start_date
        end = self._parse_date(end_raw) if end_raw is not None else leave.end_date

        if require_dates and (not start or not end):
            raise ValueError("start_date and end_date are required")
        if start and end and end < start:
            raise ValueError("end_date cannot be earlier than start_date")

        if start:
            leave.start_date = start
        if end:
            leave.end_date = end

        leave_type = payload.get("leave_type", LeaveType.OTHER.value)
        if leave_type not in {item.value for item in LeaveType}:
            raise ValueError("Invalid leave type")
        leave.leave_type = leave_type

        status = payload.get("status")
        if status:
            if status not in {item.value for item in LeaveStatus}:
                raise ValueError("Invalid leave status")
            leave.status = status

        leave.reason = payload.get("reason")

    # --------------------------------------------------------------------- #
    # Availability helpers
    # --------------------------------------------------------------------- #
    def is_member_on_leave(self, member: TeamMember, target_date: date) -> bool:
        return (
            self.db.query(MemberLeave)
            .filter(
                MemberLeave.team_member_id == member.id,
                MemberLeave.start_date <= target_date,
                MemberLeave.end_date >= target_date,
                MemberLeave.status.in_(_BLOCKING_LEAVE_STATUSES),
            )
            .first()
            is not None
        )

    def is_member_on_active_shift(self, member: TeamMember, current_dt: datetime) -> bool:
        """Check if member has an active shift covering the provided datetime."""
        # Fetch shifts only once per member
        shifts: Sequence[ShiftAssignment] = (
            self.db.query(ShiftAssignment)
            .filter(
                ShiftAssignment.team_member_id == member.id,
                ShiftAssignment.is_active.is_(True),
                or_(ShiftAssignment.effective_from.is_(None), ShiftAssignment.effective_from <= current_dt.date()),
                or_(ShiftAssignment.effective_to.is_(None), ShiftAssignment.effective_to >= current_dt.date()),
            )
            .all()
        )

        if not shifts:
            return False

        local_dt = self._to_member_timezone(member, current_dt)
        weekday = local_dt.weekday()
        current_minutes = local_dt.hour * 60 + local_dt.minute

        for shift in shifts:
            if shift.day_of_week is not None and shift.day_of_week != weekday:
                # Handle overnight shifts by checking previous day
                if not self._matches_overnight_shift(shift, local_dt, current_minutes):
                    continue
                return True

            if self._time_in_shift_window(shift, current_minutes):
                return True

        return False

    def is_member_available(self, member: TeamMember, when: Optional[datetime] = None) -> bool:
        """Determine if member can receive work at the specified datetime."""
        if not member.active:
            return False

        when = when or datetime.utcnow().replace(tzinfo=pytz.UTC)
        local_dt = self._to_member_timezone(member, when)

        # Leave check (blocks availability)
        if self.is_member_on_leave(member, local_dt.date()):
            logger.debug(f"Member {member.id} is on leave for {local_dt.date()}")
            return False

        # If shifts configured, enforce them
        has_shifts = (
            self.db.query(ShiftAssignment)
            .filter(
                ShiftAssignment.team_member_id == member.id,
                ShiftAssignment.is_active.is_(True),
            )
            .first()
            is not None
        )

        if has_shifts:
            return self.is_member_on_active_shift(member, when)

        # Fallback to default working hours / business hours
        current_hour = local_dt.hour
        if not (member.work_start_hour <= current_hour < member.work_end_hour):
            return False

        return True

    # ------------------------------------------------------------------ #
    # On-call rotation helpers
    # ------------------------------------------------------------------ #
    def assign_weekly_oncall(self, week_start: Optional[date] = None, force: bool = False) -> List[OnCallAssignment]:
        """Create weekly on-call assignments for L1 and L2 teams."""

        week_start = self._normalize_week_start(week_start or self._current_week_start())
        week_end = week_start + timedelta(days=6)

        self.ensure_standard_weekday_shifts()

        existing = (
            self.db.query(OnCallAssignment)
            .options(joinedload(OnCallAssignment.team_member))
            .filter(
                OnCallAssignment.week_start == week_start,
                OnCallAssignment.status == OnCallAssignmentStatus.SCHEDULED.value,
            )
            .all()
        )
        if existing:
            if not force:
                logger.info("📅 Reusing existing on-call assignments for %s", week_start)
                return existing
            logger.info("♻️ Force re-running on-call assignments for %s", week_start)
            for prev in existing:
                prev.status = OnCallAssignmentStatus.CANCELLED.value
                prev.replaced_by_member_id = None
                prev.replaces_assignment_id = None
                if prev.notes:
                    prev.notes = f"{prev.notes}\nForce re-run on {datetime.utcnow().isoformat()}Z"
                else:
                    prev.notes = f"Force re-run on {datetime.utcnow().isoformat()}Z"
                self._remove_oncall_shifts_for_week(prev.team_level, week_start)
                try:
                    state = self._get_rotation_state(prev.team_level)
                    if prev.rotation_position is not None:
                        state.next_position = prev.rotation_position
                except Exception as exc:  # defensive; rotation state should exist
                    logger.warning("⚠️ Unable to reset rotation state for %s: %s", prev.team_level, exc)
            self.db.flush()

        assignments: List[OnCallAssignment] = []

        for team_level in _ONCALL_TEAM_LEVELS:
            result = self._prepare_next_oncall_assignment(team_level, week_start, week_end)
            if not result:
                logger.warning("⚠️ Unable to schedule on-call coverage for %s in week %s", team_level, week_start)
                continue

            assignment: OnCallAssignment = result["assignment"]
            state: OnCallRotationState = result["state"]
            assignments.append(assignment)

            self.db.add(assignment)

            # Ensure assigned member has active standard shifts
            self._ensure_member_has_standard_shifts(assignment.team_member_id)

            # Remove prior on-call windows for this week and team before adding new coverage
            self._remove_oncall_shifts_for_week(team_level, week_start)
            self._create_oncall_shift_windows(assignment.team_member_id, team_level, week_start, week_end)

            # Advance pointer for next run
            state.next_position = result["next_position"]

        self.db.commit()

        if assignments:
            self._notify_oncall_schedule(week_start, assignments)
        else:
            logger.error("❌ No on-call assignments produced for week %s", week_start)

        return assignments

    def rotate_oncall_member(self, team_level: str, week_start: date, reason: Optional[str] = None) -> Optional[OnCallAssignment]:
        """Rotate the scheduled on-call engineer for the given week/team."""

        week_start = self._normalize_week_start(week_start)

        current_assignment = (
            self.db.query(OnCallAssignment)
            .options(joinedload(OnCallAssignment.team_member))
            .filter(
                OnCallAssignment.team_level == team_level,
                OnCallAssignment.week_start == week_start,
                OnCallAssignment.status == OnCallAssignmentStatus.SCHEDULED.value,
            )
            .first()
        )

        if not current_assignment:
            logger.warning("⚠️ No scheduled on-call assignment to rotate for %s week %s", team_level, week_start)
            return None

        result = self._prepare_next_oncall_assignment(
            team_level,
            week_start,
            current_assignment.week_end,
            exclusions={current_assignment.team_member_id},
            update_pointer=False,
        )

        if not result:
            logger.warning("⚠️ No alternate engineer available for on-call rotation (%s)", team_level)
            return None

        replacement: OnCallAssignment = result["assignment"]
        state: OnCallRotationState = result["state"]

        # Original member should remain at the head of the queue for next cycle
        if current_assignment.rotation_position is not None:
            state.next_position = current_assignment.rotation_position

        current_assignment.status = OnCallAssignmentStatus.REPLACED.value
        current_assignment.replaced_by_member_id = replacement.team_member_id
        current_assignment.notes = reason or current_assignment.notes

        # Ensure replacement member has active standard shifts
        self._ensure_member_has_standard_shifts(replacement.team_member_id)

        self._remove_oncall_shifts_for_week(team_level, week_start)
        self._create_oncall_shift_windows(replacement.team_member_id, team_level, week_start, current_assignment.week_end)

        self.db.add(replacement)
        self.db.commit()

        self._notify_oncall_rotation_change(week_start, replacement, current_assignment, reason)
        return replacement

    def manual_replace_oncall(
        self,
        assignment_id: int,
        new_member_id: int,
        reason: Optional[str] = None,
        requested_by: Optional[str] = None,
    ) -> OnCallAssignment:
        """Manually replace the on-call engineer for a scheduled assignment."""

        assignment = (
            self.db.query(OnCallAssignment)
            .options(joinedload(OnCallAssignment.team_member))
            .filter(
                OnCallAssignment.id == assignment_id,
                OnCallAssignment.status == OnCallAssignmentStatus.SCHEDULED.value,
            )
            .first()
        )

        if not assignment:
            raise ValueError("On-call assignment not found or already replaced")

        if assignment.team_member_id == new_member_id:
            raise ValueError("Engineer is already assigned to this on-call slot")

        new_member = self.db.query(TeamMember).filter(TeamMember.id == new_member_id).first()
        if not new_member or not new_member.active:
            raise ValueError("Selected engineer is not active")

        if new_member.team_level.value != assignment.team_level:
            raise ValueError("Engineer team level does not match the on-call slot")

        if self._member_unavailable_during(new_member, assignment.week_start, assignment.week_end):
            raise ValueError("Selected engineer is unavailable for the on-call window")

        replacement = OnCallAssignment(
            team_level=assignment.team_level,
            team_member_id=new_member_id,
            week_start=assignment.week_start,
            week_end=assignment.week_end,
            status=OnCallAssignmentStatus.SCHEDULED.value,
            rotation_position=None,
            replaces_assignment_id=assignment.id,
            notes=reason,
        )

        assignment.status = OnCallAssignmentStatus.REPLACED.value
        assignment.replaced_by_member_id = new_member_id
        if reason:
            assignment.notes = reason

        self.db.add(replacement)

        # Ensure new member has active standard shifts before adding on-call shifts
        self._ensure_member_has_standard_shifts(new_member_id)

        self._remove_oncall_shifts_for_week(assignment.team_level, assignment.week_start)
        self._create_oncall_shift_windows(new_member_id, assignment.team_level, assignment.week_start, assignment.week_end)

        self.db.commit()
        self.db.refresh(replacement)
        self.db.refresh(assignment)

        notify_reason = reason or "Manual replacement"
        if requested_by:
            notify_reason = f"{notify_reason} (requested by {requested_by})"

        self._notify_oncall_rotation_change(
            assignment.week_start,
            replacement,
            assignment,
            notify_reason,
        )

        return replacement

    def list_rotation_entries(self, team_level: Optional[str] = None) -> List[OnCallRotationEntry]:
        query = (
            self.db.query(OnCallRotationEntry)
            .options(joinedload(OnCallRotationEntry.team_member))
            .order_by(OnCallRotationEntry.team_level.asc(), OnCallRotationEntry.position.asc())
        )
        if team_level:
            query = query.filter(OnCallRotationEntry.team_level == team_level)
        return query.all()

    def list_oncall_assignments(self, week_start: Optional[date] = None) -> List[OnCallAssignment]:
        week_start = self._normalize_week_start(week_start or self._current_week_start())
        return (
            self.db.query(OnCallAssignment)
            .options(joinedload(OnCallAssignment.team_member))
            .filter(
                OnCallAssignment.week_start == week_start,
                OnCallAssignment.status == OnCallAssignmentStatus.SCHEDULED.value,
            )
            .order_by(OnCallAssignment.team_level.asc())
            .all()
        )

    def _prepare_next_oncall_assignment(
        self,
        team_level: str,
        week_start: date,
        week_end: date,
        exclusions: Optional[set[int]] = None,
        update_pointer: bool = True,
    ) -> Optional[Dict[str, object]]:
        exclusions = exclusions or set()

        entries = self._ensure_rotation_entries(team_level)
        if not entries:
            return None

        state = self._get_rotation_state(team_level)
        ordered_entries = sorted(entries, key=lambda e: e.position)

        total = len(ordered_entries)
        start_idx = state.next_position % total if total else 0

        eligible: List[Tuple[int, OnCallRotationEntry]] = []
        for offset in range(total):
            idx = (start_idx + offset) % total
            entry = ordered_entries[idx]
            if not entry.active or entry.team_member is None:
                continue
            if entry.team_member_id in exclusions:
                continue
            if not entry.team_member.active:
                continue
            if self._member_unavailable_during(entry.team_member, week_start, week_end):
                continue
            eligible.append((idx, entry))

        if not eligible:
            return None

        random.shuffle(eligible)
        candidate_index, candidate_entry = eligible[0]

        if not candidate_entry:
            return None

        assignment = OnCallAssignment(
            team_level=team_level,
            team_member_id=candidate_entry.team_member_id,
            week_start=week_start,
            week_end=week_end,
            status=OnCallAssignmentStatus.SCHEDULED.value,
            rotation_position=candidate_entry.position,
        )

        next_position = (candidate_index + 1) % total
        if update_pointer:
            state.next_position = next_position

        return {
            "assignment": assignment,
            "state": state,
            "next_position": next_position,
        }

    def _remove_oncall_shifts_for_week(self, team_level: str, week_start: date):
        to_remove = (
            self.db.query(ShiftAssignment)
            .filter(
                ShiftAssignment.category == _ONCALL_SHIFT_CATEGORY,
                ShiftAssignment.team_level == team_level,
                ShiftAssignment.generated_week_start == week_start,
            )
            .all()
        )
        for shift in to_remove:
            self.db.delete(shift)

    def _create_oncall_shift_windows(
        self,
        member_id: int,
        team_level: str,
        week_start: date,
        week_end: date,
    ):
        member = self.db.query(TeamMember).filter(TeamMember.id == member_id).first()
        if not member:
            logger.error("❌ Cannot create on-call shifts for missing member %s", member_id)
            return

        # Weekday after-hours coverage (20:00-09:00 next day)
        for day in range(0, 5):
            shift = ShiftAssignment(
                team_member_id=member_id,
                team_level=team_level,
                day_of_week=day,
                start_hour=20,
                start_minute=0,
                end_hour=9,
                end_minute=0,
                timezone=member.timezone,
                priority=25,
                is_active=True,
                category=_ONCALL_SHIFT_CATEGORY,
                generated_week_start=week_start,
            )
            self.db.add(shift)

        # Weekend full-day coverage (Saturday/Sunday)
        for day in (5, 6):
            shift = ShiftAssignment(
                team_member_id=member_id,
                team_level=team_level,
                day_of_week=day,
                start_hour=0,
                start_minute=0,
                end_hour=0,
                end_minute=0,
                timezone=member.timezone,
                priority=25,
                is_active=True,
                category=_ONCALL_SHIFT_CATEGORY,
                generated_week_start=week_start,
            )
            self.db.add(shift)

    def _ensure_rotation_entries(self, team_level: str) -> List[OnCallRotationEntry]:
        entries = (
            self.db.query(OnCallRotationEntry)
            .options(joinedload(OnCallRotationEntry.team_member))
            .filter(OnCallRotationEntry.team_level == team_level)
            .order_by(OnCallRotationEntry.position.asc())
            .all()
        )

        if entries:
            return entries

        # Bootstrap using active members if no rotation defined
        members = (
            self.db.query(TeamMember)
            .filter(
                TeamMember.team_level == TeamLevel(team_level),
                TeamMember.active.is_(True),
            )
            .order_by(TeamMember.id.asc())
            .all()
        )

        for idx, member in enumerate(members):
            entry = OnCallRotationEntry(
                team_level=team_level,
                team_member_id=member.id,
                position=idx,
                active=True,
            )
            self.db.add(entry)
        if members:
            self.db.commit()

        return (
            self.db.query(OnCallRotationEntry)
            .options(joinedload(OnCallRotationEntry.team_member))
            .filter(OnCallRotationEntry.team_level == team_level)
            .order_by(OnCallRotationEntry.position.asc())
            .all()
        )

    def _get_rotation_state(self, team_level: str) -> OnCallRotationState:
        state = (
            self.db.query(OnCallRotationState)
            .filter(OnCallRotationState.team_level == team_level)
            .first()
        )
        if not state:
            state = OnCallRotationState(team_level=team_level, next_position=0)
            self.db.add(state)
            self.db.commit()
        return state

    def _member_unavailable_during(self, member: TeamMember, start: date, end: date) -> bool:
        leave_exists = (
            self.db.query(MemberLeave)
            .filter(
                MemberLeave.team_member_id == member.id,
                MemberLeave.status.in_(_BLOCKING_LEAVE_STATUSES),
                MemberLeave.end_date >= start,
                MemberLeave.start_date <= end,
            )
            .first()
            is not None
        )
        return leave_exists

    def _notify_oncall_schedule(self, week_start: date, assignments: List[OnCallAssignment]):
        notification_service = NotificationService(self.db)
        if not notification_service.google_chat_enabled:
            return

        rotation_links = self._build_rotation_links(assignments, week_start)
        notification_service.send_oncall_rotation_summary(week_start, assignments, rotation_links)

    def _notify_oncall_rotation_change(
        self,
        week_start: date,
        replacement: OnCallAssignment,
        previous: OnCallAssignment,
        reason: Optional[str],
    ):
        notification_service = NotificationService(self.db)
        if not notification_service.google_chat_enabled:
            return

        notification_service.send_oncall_rotation_update(week_start, replacement, previous, reason, self._build_rotation_links([replacement], week_start))

    def _build_rotation_links(self, assignments: List[OnCallAssignment], week_start: date) -> Dict[str, Optional[str]]:
        base_url = getattr(settings, "PUBLIC_API_BASE_URL", None)
        if not base_url:
            return {assignment.team_level: None for assignment in assignments}

        links: Dict[str, Optional[str]] = {}
        for assignment in assignments:
            token = self.generate_rotation_token(assignment.team_level, week_start)
            links[assignment.team_level] = f"{base_url.rstrip('/')}/api/v1/oncall/rotate?team_level={assignment.team_level}&week_start={week_start.isoformat()}&token={token}"
        return links

    @staticmethod
    def generate_rotation_token(team_level: str, week_start: date) -> str:
        payload = f"{team_level}:{week_start.isoformat()}".encode()
        secret = settings.SECRET_KEY.encode()
        digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return digest

    @staticmethod
    def verify_rotation_token(team_level: str, week_start: date, token: str) -> bool:
        expected = SchedulingService.generate_rotation_token(team_level, week_start)
        return hmac.compare_digest(expected, token)

    @staticmethod
    def _current_week_start() -> date:
        today = datetime.utcnow().date()
        return today - timedelta(days=today.weekday())

    @staticmethod
    def _normalize_week_start(week_start: date) -> date:
        return week_start - timedelta(days=week_start.weekday())

    # ------------------------------------------------------------------ #
    # Serializers
    # ------------------------------------------------------------------ #
    @staticmethod
    def serialize_shift(shift: ShiftAssignment) -> Dict:
        member = shift.team_member
        return {
            "id": shift.id,
            "team_member_id": shift.team_member_id,
            "team_member_name": member.name if member else None,
            "team_level": shift.team_level or (member.team_level.value if member else None),
            "day_of_week": shift.day_of_week,
            "start_hour": shift.start_hour,
            "start_minute": shift.start_minute,
            "end_hour": shift.end_hour,
            "end_minute": shift.end_minute,
            "timezone": shift.timezone,
            "effective_from": shift.effective_from.isoformat() if shift.effective_from else None,
            "effective_to": shift.effective_to.isoformat() if shift.effective_to else None,
            "priority": shift.priority,
            "is_active": shift.is_active,
            "notes": shift.notes,
            "category": shift.category,
            "generated_week_start": shift.generated_week_start.isoformat() if shift.generated_week_start else None,
            "created_at": shift.created_at.isoformat() if shift.created_at else None,
            "updated_at": shift.updated_at.isoformat() if shift.updated_at else None,
        }

    @staticmethod
    def serialize_rotation_entry(entry: OnCallRotationEntry) -> Dict:
        member = entry.team_member
        return {
            "id": entry.id,
            "team_level": entry.team_level,
            "team_member_id": entry.team_member_id,
            "team_member_name": member.name if member else None,
            "position": entry.position,
            "active": entry.active,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
        }

    @staticmethod
    def serialize_oncall_assignment(assignment: OnCallAssignment) -> Dict:
        member = assignment.team_member
        return {
            "id": assignment.id,
            "team_level": assignment.team_level,
            "team_member_id": assignment.team_member_id,
            "team_member_name": member.name if member else None,
            "week_start": assignment.week_start.isoformat(),
            "week_end": assignment.week_end.isoformat(),
            "status": assignment.status,
            "rotation_position": assignment.rotation_position,
            "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
            "updated_at": assignment.updated_at.isoformat() if assignment.updated_at else None,
        }

    @staticmethod
    def serialize_leave(leave: MemberLeave) -> Dict:
        member = leave.team_member
        return {
            "id": leave.id,
            "team_member_id": leave.team_member_id,
            "team_member_name": member.name if member else None,
            "team_level": member.team_level.value if member else None,
            "start_date": leave.start_date.isoformat(),
            "end_date": leave.end_date.isoformat(),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "reason": leave.reason,
            "created_by": leave.created_by,
            "approved_by": leave.approved_by,
            "approved_at": leave.approved_at.isoformat() if leave.approved_at else None,
            "created_at": leave.created_at.isoformat() if leave.created_at else None,
            "updated_at": leave.updated_at.isoformat() if leave.updated_at else None,
        }

    # ------------------------------------------------------------------ #
    # Internal utilities
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parse_date(value) -> Optional[date]:
        if value in (None, "", "null"):
            return None
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(str(value)).date()

    @staticmethod
    def _to_member_timezone(member: TeamMember, when: datetime) -> datetime:
        tz = pytz.timezone(member.timezone or "UTC")
        if when.tzinfo is None:
            when = when.replace(tzinfo=pytz.UTC)
        return when.astimezone(tz)

    @staticmethod
    def _time_in_shift_window(shift: ShiftAssignment, minutes: int) -> bool:
        """Check if minutes since midnight falls within shift window."""
        start_total = shift.start_hour * 60 + shift.start_minute
        end_total = shift.end_hour * 60 + shift.end_minute

        if end_total == start_total:
            return True

        if end_total > start_total:
            return start_total <= minutes < end_total

        # Overnight shift (wrap around midnight)
        return minutes >= start_total or minutes < end_total

    def _matches_overnight_shift(
        self,
        shift: ShiftAssignment,
        local_dt: datetime,
        current_minutes: int,
    ) -> bool:
        """Handle overnight shifts by checking previous-day assignments."""
        if not self._time_in_shift_window(shift, current_minutes):
            return False

        # If shift wraps to next day, allow when current weekday is successor of configured day
        if shift.day_of_week is None:
            return True

        start_total = shift.start_hour * 60 + shift.start_minute
        end_total = shift.end_hour * 60 + shift.end_minute
        if end_total == start_total:
            return True
        if end_total > start_total:
            return False  # not overnight

        yesterday = (local_dt.weekday() - 1) % 7
        return shift.day_of_week == yesterday
