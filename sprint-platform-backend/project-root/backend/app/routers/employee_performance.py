"""Read-only project and sprint employee performance reports."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Comment,
    Deployment,
    Employee,
    Issue,
    IssueHistory,
    Project,
    ProjectMember,
    Requirement,
    RequirementTraceLink,
    Sprint,
    TestResult,
)
from app.schemas.employee_performance import EmployeePerformanceReport
from app.services.employee_performance_service import EmployeePerformanceService


router = APIRouter(prefix="/projects", tags=["Employee Performance"])


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


def _load_related_records(
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

    histories: dict[uuid.UUID, list[IssueHistory]] = defaultdict(list)
    for item in db.scalars(
        select(IssueHistory)
        .where(IssueHistory.issue_id.in_(issue_ids))
        .order_by(IssueHistory.changed_at, IssueHistory.id)
    ):
        histories[item.issue_id].append(item)

    tests: dict[uuid.UUID, list[TestResult]] = defaultdict(list)
    for item in db.scalars(select(TestResult).where(TestResult.issue_id.in_(issue_ids))):
        tests[item.issue_id].append(item)

    deployments: dict[uuid.UUID, list[Deployment]] = defaultdict(list)
    for item in db.scalars(select(Deployment).where(Deployment.issue_id.in_(issue_ids))):
        deployments[item.issue_id].append(item)

    comments = list(db.scalars(select(Comment).where(Comment.issue_id.in_(issue_ids))))
    return histories, tests, deployments, comments


def _load_requirement_records(
    db: Session,
    project_id: uuid.UUID,
) -> tuple[list[RequirementTraceLink], dict[uuid.UUID, Requirement]]:
    rows = list(
        db.execute(
            select(RequirementTraceLink, Requirement)
            .join(Requirement, Requirement.id == RequirementTraceLink.requirement_id)
            .where(
                RequirementTraceLink.project_id == project_id,
                Requirement.project_id == project_id,
            )
        )
    )
    return [link for link, _ in rows], {requirement.id: requirement for _, requirement in rows}


def _build_report(
    db: Session,
    project: Project,
    employee: Employee,
    *,
    sprint: Sprint | None = None,
) -> EmployeePerformanceReport:
    statement = select(Issue).where(Issue.project_id == project.id).order_by(Issue.issue_key)
    if sprint is not None:
        statement = statement.where(Issue.sprint_id == sprint.id)
    issues = list(db.scalars(statement))
    histories, tests, deployments, comments = _load_related_records(db, issues)
    trace_links, requirements_by_id = _load_requirement_records(db, project.id)
    return EmployeePerformanceService.build_report(
        employee,
        project,
        issues,
        histories,
        tests,
        deployments,
        comments,
        trace_links,
        requirements_by_id,
        sprint=sprint,
    )


@router.get(
    "/{project_key}/employees/{employee_id}/performance",
    response_model=EmployeePerformanceReport,
)
def get_project_employee_performance(
    project_key: str,
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmployeePerformanceReport:
    project = _get_project(db, project_key)
    employee = _get_employee(db, employee_id)
    _validate_project_member(db, project.id, employee.id)
    return _build_report(db, project, employee)


@router.get(
    "/{project_key}/sprints/{sprint_id}/employees/{employee_id}/performance",
    response_model=EmployeePerformanceReport,
)
def get_sprint_employee_performance(
    project_key: str,
    sprint_id: uuid.UUID,
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EmployeePerformanceReport:
    project = _get_project(db, project_key)
    employee = _get_employee(db, employee_id)
    _validate_project_member(db, project.id, employee.id)
    sprint = _get_sprint(db, project.id, sprint_id)
    return _build_report(db, project, employee, sprint=sprint)
