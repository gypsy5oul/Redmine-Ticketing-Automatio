#!/usr/bin/env python3
"""
Scheduling API - shift calendar and leave management endpoints.
"""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    require_admin,
    require_manager,
)
from app.core.database import get_db
from app.models.schedule import LeaveStatus, LeaveType, MemberLeave
from app.models.team import TeamMember, TeamLevel
from app.models.user import User, UserRole
from app.services.scheduling_service import SchedulingService

router = APIRouter(prefix="/api/v1", tags=["Scheduling"])


# --------------------------------------------------------------------------- #
# Pydantic payloads
# --------------------------------------------------------------------------- #
class ShiftRequest(BaseModel):
    team_member_id: int
    team_level: Optional[str] = None
    day_of_week: Optional[int] = None
    start_hour: int
    start_minute: int = 0
    end_hour: int
    end_minute: int = 0
    timezone: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    priority: Optional[int] = 50
    is_active: Optional[bool] = True
    notes: Optional[str] = None

    @validator("day_of_week")
    def validate_day(cls, value):
        if value is not None and value not in range(0, 7):
            raise ValueError("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        return value


class ShiftUpdateRequest(BaseModel):
    team_member_id: Optional[int] = None
    team_level: Optional[str] = None
    day_of_week: Optional[int] = None
    start_hour: Optional[int] = None
    start_minute: Optional[int] = None
    end_hour: Optional[int] = None
    end_minute: Optional[int] = None
    timezone: Optional[str] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

    @validator("day_of_week")
    def validate_day(cls, value):
        if value is not None and value not in range(0, 7):
            raise ValueError("day_of_week must be between 0 and 6")
        return value


class LeaveRequest(BaseModel):
    start_date: date
    end_date: date
    leave_type: Optional[str] = LeaveType.OTHER.value
    status: Optional[str] = None  # Changed: No default status - let backend decide based on role
    reason: Optional[str] = None
    team_member_id: Optional[int] = None

    @validator("leave_type")
    def validate_type(cls, value):
        if value not in {t.value for t in LeaveType}:
            raise ValueError("Invalid leave_type")
        return value

    @validator("status")
    def validate_status(cls, value):
        if value and value not in {s.value for s in LeaveStatus}:
            raise ValueError("Invalid status")
        return value


class LeaveUpdateRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    leave_type: Optional[str] = None
    status: Optional[str] = None
    reason: Optional[str] = None

    @validator("leave_type")
    def validate_type(cls, value):
        if value and value not in {t.value for t in LeaveType}:
            raise ValueError("Invalid leave_type")
        return value


class OnCallRunRequest(BaseModel):
    week_start: Optional[date] = None
    force: bool = False


class OnCallReplaceRequest(BaseModel):
    team_member_id: int
    reason: Optional[str] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_team_member_for_user(db: Session, user: User) -> Optional[TeamMember]:
    return db.query(TeamMember).filter(TeamMember.user_id == user.id).first()


def _ensure_member_exists(member: Optional[TeamMember]):
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated team member record not found",
        )


def _user_can_manage_or_delete_leaves(db: Session, user: User) -> bool:
    if user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER}:
        return True
    try:
        member = _get_team_member_for_user(db, user)
    except HTTPException:
        return False
    return member.team_level == TeamLevel.L3


# --------------------------------------------------------------------------- #
# Shift endpoints
# --------------------------------------------------------------------------- #
@router.get("/shifts")
async def list_shifts(
    team_level: Optional[str] = Query(default=None),
    member_id: Optional[int] = Query(default=None),
    include_inactive: bool = Query(default=False),
    grouped: bool = Query(default=False, description="Group shifts by team member"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    service = SchedulingService(db)
    if team_level:
        try:
            TeamLevel(team_level)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid team_level value")
    shifts = service.list_shift_assignments(
        team_level=team_level,
        member_id=member_id,
        include_inactive=include_inactive,
    )

    if grouped:
        # Group shifts by team member
        grouped_data = {}
        for shift in shifts:
            member_id = shift.team_member_id
            if member_id not in grouped_data:
                grouped_data[member_id] = {
                    "team_member_id": member_id,
                    "team_member_name": shift.team_member.name if shift.team_member else None,
                    "team_level": shift.team_level or (shift.team_member.team_level.value if shift.team_member else None),
                    "timezone": shift.timezone,
                    "is_active": True,
                    "shifts": [],
                    "active_count": 0,
                    "total_count": 0,
                }

            grouped_data[member_id]["shifts"].append(service.serialize_shift(shift))
            grouped_data[member_id]["total_count"] += 1
            if shift.is_active:
                grouped_data[member_id]["active_count"] += 1

        # Set group is_active based on majority (>50% active shifts)
        for member_id, data in grouped_data.items():
            data["is_active"] = data["active_count"] > (data["total_count"] / 2)
            # Clean up counts from response
            del data["active_count"]
            del data["total_count"]

        result = list(grouped_data.values())
        return {"count": len(result), "grouped_shifts": result}
    else:
        data = [service.serialize_shift(shift) for shift in shifts]
        return {"count": len(data), "shifts": data}


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
async def create_shift(
    payload: ShiftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if payload.team_level:
        try:
            TeamLevel(payload.team_level)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid team_level value")
    service = SchedulingService(db)
    shift = service.create_shift(payload.dict(exclude_unset=True), created_by=current_user.username)
    return {"shift": service.serialize_shift(shift)}


@router.put("/shifts/{shift_id}")
async def update_shift(
    shift_id: int,
    payload: ShiftUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = SchedulingService(db)
    shift = service.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    if payload.team_level:
        try:
            TeamLevel(payload.team_level)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid team_level value")

    updated = service.update_shift(shift, payload.dict(exclude_unset=True))
    return {"shift": service.serialize_shift(updated)}


@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = SchedulingService(db)
    shift = service.get_shift(shift_id)
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    service.delete_shift(shift)
    return {}


# --------------------------------------------------------------------------- #
# Leave endpoints
# --------------------------------------------------------------------------- #
@router.get("/leaves")
async def list_leaves(
    team_level: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_past: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)
    if not _user_can_manage_or_delete_leaves(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view team leave entries",
        )
    if team_level:
        try:
            TeamLevel(team_level)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid team_level value")

    leaves = service.list_leaves(
        team_level=team_level,
        status=status_filter,
        include_past=include_past,
    )
    data = [service.serialize_leave(leave) for leave in leaves]
    return {"count": len(data), "leaves": data}


@router.get("/leaves/me")
async def list_my_leaves(
    include_past: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)
    member = _get_team_member_for_user(db, current_user)
    _ensure_member_exists(member)

    leaves = service.list_leaves(member_id=member.id, include_past=include_past)
    data = [service.serialize_leave(leave) for leave in leaves]
    return {"count": len(data), "leaves": data}


@router.post("/leaves", status_code=status.HTTP_201_CREATED)
async def create_leave(
    payload: LeaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)

    target_member_id = payload.team_member_id
    is_manager_or_above = current_user.role in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER}

    if target_member_id:
        # Only managers/admins can create leave on behalf of others
        if not is_manager_or_above:
            raise HTTPException(status_code=403, detail="Insufficient permissions to create leave for another member")
        member = db.query(TeamMember).filter(TeamMember.id == target_member_id).first()
        # When managers create leave for others, auto-approve
        auto_approve = True
    else:
        # L1/L2 creating their own leave
        member = _get_team_member_for_user(db, current_user)
        # L1/L2 leave requests require approval
        auto_approve = is_manager_or_above

    _ensure_member_exists(member)

    leave_payload = payload.dict(exclude_unset=True, exclude={"team_member_id"})

    # Remove status from payload - let service decide based on auto_approve
    leave_payload.pop("status", None)

    leave = service.create_leave(
        member,
        leave_payload,
        created_by=current_user.username,
        auto_approve=auto_approve,
    )
    return {"leave": service.serialize_leave(leave)}


@router.put("/leaves/{leave_id}")
async def update_leave(
    leave_id: int,
    payload: LeaveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)
    leave = service.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    member = leave.team_member

    # Allow updates if user owns the leave or has elevated permissions
    if current_user.role not in {UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER}:
        member_record = _get_team_member_for_user(db, current_user)
        if not member_record or member_record.id != leave.team_member_id:
            raise HTTPException(status_code=403, detail="You can only update your own leave entries")

    updated = service.update_leave(leave, payload.dict(exclude_unset=True))
    return {"leave": service.serialize_leave(updated)}


@router.post("/leaves/{leave_id}/status")
async def update_leave_status(
    leave_id: int,
    status_update: LeaveUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    if not status_update.status:
        raise HTTPException(status_code=400, detail="status is required")

    desired_status = LeaveStatus(status_update.status)
    if desired_status not in {LeaveStatus.APPROVED, LeaveStatus.REJECTED, LeaveStatus.CANCELLED}:
        raise HTTPException(status_code=400, detail="Unsupported status transition")

    service = SchedulingService(db)
    leave = service.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    service.set_leave_status(leave, desired_status, approved_by=current_user.username)
    return {"leave": service.serialize_leave(leave)}


@router.delete("/leaves/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)
    leave = service.get_leave(leave_id)
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    if not _user_can_manage_or_delete_leaves(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete leave entries",
        )

    service.delete_leave(leave)
    return {}


# --------------------------------------------------------------------------- #
# On-call rotation management
# --------------------------------------------------------------------------- #


@router.get("/oncall/rotation")
async def get_oncall_rotation(
    team_level: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    service = SchedulingService(db)
    entries = service.list_rotation_entries(team_level)
    return {
        "count": len(entries),
        "entries": [service.serialize_rotation_entry(entry) for entry in entries],
    }


@router.get("/oncall/assignments")
async def get_oncall_assignments(
    week_start: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = SchedulingService(db)
    assignments = service.list_oncall_assignments(week_start)
    return {
        "count": len(assignments),
        "assignments": [service.serialize_oncall_assignment(a) for a in assignments],
    }


@router.post("/oncall/assignments/run")
async def run_oncall_assignment(
    payload: OnCallRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    service = SchedulingService(db)
    assignments = service.assign_weekly_oncall(
        week_start=payload.week_start,
        force=payload.force,
    )
    return {
        "success": True,
        "count": len(assignments),
        "assignments": [service.serialize_oncall_assignment(a) for a in assignments],
    }


@router.get("/oncall/rotate")
async def rotate_oncall_from_link(
    team_level: str,
    week_start: date,
    token: str,
    reason: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    if not SchedulingService.verify_rotation_token(team_level, week_start, token):
        raise HTTPException(status_code=403, detail="Invalid rotation token")

    service = SchedulingService(db)
    replacement = service.rotate_oncall_member(team_level, week_start, reason)
    if not replacement:
        raise HTTPException(status_code=404, detail="No rotation candidate available")

    return {
        "success": True,
        "message": (
            f"On-call rotation updated for {team_level}. "
            f"New engineer: {replacement.team_member.name if replacement.team_member else 'Unassigned'}"
        ),
    }


@router.post("/oncall/assignments/{assignment_id}/replace")
async def replace_oncall_assignment(
    assignment_id: int,
    payload: OnCallReplaceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = SchedulingService(db)
    try:
        replacement = service.manual_replace_oncall(
            assignment_id,
            payload.team_member_id,
            reason=payload.reason,
            requested_by=current_user.username,
        )
    except ValueError as exc:  # validation/availability issues
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {
        "success": True,
        "assignment": service.serialize_oncall_assignment(replacement),
    }
