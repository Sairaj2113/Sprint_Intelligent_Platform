from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Issue, IssueHistory, Project, Sprint
from app.schemas.kpi import (
    AggregateDurationMetrics,
    BugMetrics,
    IssueMetrics,
    ProjectKpiResponse,
    SprintKpiResponse,
    StatusDistribution,
    StoryPointMetrics,
)
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_bug_metrics,
    calculate_issue_duration_metrics,
    calculate_issue_metrics,
    calculate_status_distribution,
    calculate_story_point_metrics,
)

router = APIRouter(prefix="/projects", tags=["KPIs"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _load_issue_histories(
    db: Session,
    issues: Iterable[Issue],
) -> dict[uuid.UUID, list[IssueHistory]]:
    issue_ids = [issue.id for issue in issues]
    if not issue_ids:
        return {}

    histories = db.scalars(
        select(IssueHistory)
        .where(IssueHistory.issue_id.in_(issue_ids))
        .order_by(IssueHistory.changed_at)
    )
    histories_by_issue: dict[uuid.UUID, list[IssueHistory]] = defaultdict(list)
    for history in histories:
        histories_by_issue[history.issue_id].append(history)
    return histories_by_issue


def _calculate_kpi_groups(
    issues: list[Issue],
    histories_by_issue: dict[uuid.UUID, list[IssueHistory]],
) -> tuple[
    IssueMetrics,
    StoryPointMetrics,
    BugMetrics,
    StatusDistribution,
    AggregateDurationMetrics,
]:
    per_issue_durations = [
        calculate_issue_duration_metrics(histories_by_issue.get(issue.id, []))
        for issue in issues
    ]
    return (
        calculate_issue_metrics(issues),
        calculate_story_point_metrics(issues),
        calculate_bug_metrics(issues),
        calculate_status_distribution(issues),
        calculate_aggregate_duration_metrics(per_issue_durations),
    )


@router.get("/{project_key}/kpis", response_model=ProjectKpiResponse)
def get_project_kpis(
    project_key: str,
    db: Session = Depends(get_db),
) -> ProjectKpiResponse:
    project = _get_project(db, project_key)
    issues = list(db.scalars(select(Issue).where(Issue.project_id == project.id)))
    histories_by_issue = _load_issue_histories(db, issues)
    (
        issue_metrics,
        story_point_metrics,
        bug_metrics,
        status_distribution,
        duration_metrics,
    ) = _calculate_kpi_groups(issues, histories_by_issue)
    return ProjectKpiResponse(
        project_id=project.id,
        project_key=project.project_key,
        issue_metrics=issue_metrics,
        story_point_metrics=story_point_metrics,
        bug_metrics=bug_metrics,
        status_distribution=status_distribution,
        duration_metrics=duration_metrics,
    )


@router.get("/{project_key}/sprints/{sprint_id}/kpis", response_model=SprintKpiResponse)
def get_sprint_kpis(
    project_key: str,
    sprint_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SprintKpiResponse:
    project = _get_project(db, project_key)
    sprint = db.scalar(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project.id)
    )
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")

    issues = list(db.scalars(select(Issue).where(Issue.sprint_id == sprint.id)))
    histories_by_issue = _load_issue_histories(db, issues)
    (
        issue_metrics,
        story_point_metrics,
        bug_metrics,
        status_distribution,
        duration_metrics,
    ) = _calculate_kpi_groups(issues, histories_by_issue)
    return SprintKpiResponse(
        sprint_id=sprint.id,
        sprint_name=sprint.name,
        sprint_status=sprint.status,
        issue_metrics=issue_metrics,
        story_point_metrics=story_point_metrics,
        bug_metrics=bug_metrics,
        status_distribution=status_distribution,
        duration_metrics=duration_metrics,
    )
