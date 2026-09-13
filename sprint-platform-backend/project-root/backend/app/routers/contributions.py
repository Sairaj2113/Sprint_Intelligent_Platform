from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Comment, Deployment, Employee, Issue, IssueHistory, Project, ProjectMember, Sprint, TestResult
from app.schemas.contribution import EmployeeContributionEvidence
from app.services.contribution_service import build_employee_contribution_evidence

router = APIRouter(prefix="/projects", tags=["Contributions"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_employee(db: Session, employee_id: uuid.UUID) -> Employee:
    employee = db.scalar(select(Employee).where(Employee.id == employee_id))
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


def _validate_project_member(db: Session, project_id: uuid.UUID, employee_id: uuid.UUID) -> None:
    member_id = db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id,
            ProjectMember.employee_id == employee_id,
        )
    )
    if member_id is None:
        raise HTTPException(status_code=404, detail="Project member not found")


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
    list[Comment],
]:
    issue_ids = [issue.id for issue in issues]
    if not issue_ids:
        return {}, {}, {}, []

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

    comments = list(db.scalars(select(Comment).where(Comment.issue_id.in_(issue_ids))))
    return histories_by_issue, tests_by_issue, deployments_by_issue, comments


@router.get(
    "/{project_key}/employees/{employee_id}/contribution",
    response_model=EmployeeContributionEvidence,
)
def get_project_employee_contribution(
    project_key: str,
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmployeeContributionEvidence:
    project = _get_project(db, project_key)
    employee = _get_employee(db, employee_id)
    _validate_project_member(db, project.id, employee.id)
    issues = list(db.scalars(select(Issue).where(Issue.project_id == project.id)))
    histories_by_issue, tests_by_issue, deployments_by_issue, comments = _load_supporting_evidence(
        db, issues
    )
    sprint_names_by_id = {
        sprint.id: sprint.name
        for sprint in db.scalars(select(Sprint).where(Sprint.project_id == project.id))
    }
    return build_employee_contribution_evidence(
        employee,
        project,
        issues,
        histories_by_issue,
        tests_by_issue,
        deployments_by_issue,
        comments,
        sprint_names_by_id=sprint_names_by_id,
    )


@router.get(
    "/{project_key}/sprints/{sprint_id}/employees/{employee_id}/contribution",
    response_model=EmployeeContributionEvidence,
)
def get_sprint_employee_contribution(
    project_key: str,
    sprint_id: uuid.UUID,
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmployeeContributionEvidence:
    project = _get_project(db, project_key)
    employee = _get_employee(db, employee_id)
    _validate_project_member(db, project.id, employee.id)
    sprint = _get_sprint(db, project.id, sprint_id)
    issues = list(db.scalars(select(Issue).where(Issue.sprint_id == sprint.id)))
    histories_by_issue, tests_by_issue, deployments_by_issue, comments = _load_supporting_evidence(
        db, issues
    )
    return build_employee_contribution_evidence(
        employee,
        project,
        issues,
        histories_by_issue,
        tests_by_issue,
        deployments_by_issue,
        comments,
        sprint=sprint,
    )
