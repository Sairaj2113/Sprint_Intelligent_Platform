from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Deployment, Issue, IssueHistory, Project, Sprint, TestResult
from app.schemas.workflow import ProjectWorkflowEvidenceResponse, SprintWorkflowEvidenceResponse
from app.services.workflow_service import build_workflow_evidence

router = APIRouter(prefix="/projects", tags=["Workflow Evidence"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_sprint(db: Session, project_id: uuid.UUID, sprint_id: uuid.UUID) -> Sprint:
    sprint = db.scalar(
        select(Sprint).where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    if sprint is None:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return sprint


def _load_supporting_evidence(
    db: Session,
    issues: Iterable[Issue],
) -> tuple[
    dict[uuid.UUID, list[IssueHistory]],
    dict[uuid.UUID, list[TestResult]],
    dict[uuid.UUID, list[Deployment]],
]:
    issue_ids = [issue.id for issue in issues]
    if not issue_ids:
        return {}, {}, {}

    histories_by_issue: dict[uuid.UUID, list[IssueHistory]] = defaultdict(list)
    for history in db.scalars(
        select(IssueHistory).where(IssueHistory.issue_id.in_(issue_ids))
    ):
        histories_by_issue[history.issue_id].append(history)

    tests_by_issue: dict[uuid.UUID, list[TestResult]] = defaultdict(list)
    for test_result in db.scalars(
        select(TestResult).where(TestResult.issue_id.in_(issue_ids))
    ):
        tests_by_issue[test_result.issue_id].append(test_result)

    deployments_by_issue: dict[uuid.UUID, list[Deployment]] = defaultdict(list)
    for deployment in db.scalars(
        select(Deployment).where(Deployment.issue_id.in_(issue_ids))
    ):
        deployments_by_issue[deployment.issue_id].append(deployment)
    return histories_by_issue, tests_by_issue, deployments_by_issue


@router.get("/{project_key}/workflow", response_model=ProjectWorkflowEvidenceResponse)
def get_project_workflow_evidence(
    project_key: str,
    db: Session = Depends(get_db),
) -> ProjectWorkflowEvidenceResponse:
    project = _get_project(db, project_key)
    issues = list(db.scalars(select(Issue).where(Issue.project_id == project.id)))
    histories_by_issue, tests_by_issue, deployments_by_issue = _load_supporting_evidence(db, issues)
    sprint_names_by_id = {
        sprint.id: sprint.name
        for sprint in db.scalars(select(Sprint).where(Sprint.project_id == project.id))
    }
    response = build_workflow_evidence(
        project,
        issues,
        histories_by_issue,
        tests_by_issue,
        deployments_by_issue,
        sprint_names_by_id=sprint_names_by_id,
    )
    assert isinstance(response, ProjectWorkflowEvidenceResponse)
    return response


@router.get(
    "/{project_key}/sprints/{sprint_id}/workflow",
    response_model=SprintWorkflowEvidenceResponse,
)
def get_sprint_workflow_evidence(
    project_key: str,
    sprint_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> SprintWorkflowEvidenceResponse:
    project = _get_project(db, project_key)
    sprint = _get_sprint(db, project.id, sprint_id)
    issues = list(db.scalars(select(Issue).where(Issue.sprint_id == sprint.id)))
    histories_by_issue, tests_by_issue, deployments_by_issue = _load_supporting_evidence(db, issues)
    response = build_workflow_evidence(
        project,
        issues,
        histories_by_issue,
        tests_by_issue,
        deployments_by_issue,
        sprint=sprint,
    )
    assert isinstance(response, SprintWorkflowEvidenceResponse)
    return response
