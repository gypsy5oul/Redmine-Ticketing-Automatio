#!/usr/bin/env python3
"""
Project analytics endpoints.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.project import (
    ProjectDetailResponse,
    ProjectSummaryListResponse,
)
from app.services.project_service import (
    ProjectAnalyticsService,
    schedule_ai_insight_generation,
)

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.get(
    "",
    response_model=ProjectSummaryListResponse,
    summary="List Jira projects with ticket metrics",
)
def list_projects(
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),  # keep access restricted to authenticated users
):
    service = ProjectAnalyticsService(db)
    summaries = service.get_project_summaries()

    if limit and len(summaries) > limit:
        summaries = summaries[:limit]

    return ProjectSummaryListResponse(projects=summaries, count=len(summaries))


@router.get(
    "/{project_jira_id}",
    response_model=ProjectDetailResponse,
    summary="Get detailed metrics for a Jira project",
)
def get_project_detail(
    project_jira_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    service = ProjectAnalyticsService(db)
    detail = service.get_project_detail(project_jira_id)

    if not detail:
        raise HTTPException(status_code=404, detail="Project not found")

    if not detail.ai_insights:
        schedule_ai_insight_generation(detail, background_tasks)

    return ProjectDetailResponse(project=detail)
