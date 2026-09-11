from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Comment, Deployment, Employee, Issue, IssueHistory, Project, TestResult
from app.models.issue import IssueStatus, IssueType
from app.schemas.comment import CommentResponse
from app.schemas.deployment import DeploymentResponse
from app.schemas.history import IssueHistoryResponse
from app.schemas.issue import (
    IssueResponse,
    IssueStatusTransitionResponse,
    IssueStatusUpdateRequest,
)
from app.schemas.test_result import TestResultResponse

router = APIRouter(tags=["Issues"])


def _issue_options():
    return (
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.parent_issue),
        selectinload(Issue.sprint),
    )


def _get_issue(db: Session, issue_key: str) -> Issue:
    issue = db.scalar(
        select(Issue).options(*_issue_options()).where(Issue.issue_key == issue_key)
    )
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


def _get_project_id(db: Session, project_key: str) -> uuid.UUID:
    project_id = db.scalar(select(Project.id).where(Project.project_key == project_key))
    if project_id is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_id


@router.get("/projects/{project_key}/issues", response_model=list[IssueResponse])
def list_project_issues(
    project_key: str,
    sprint_id: uuid.UUID | None = None,
    status: IssueStatus | None = None,
    issue_type: IssueType | None = None,
    assignee_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> list[Issue]:
    project_id = _get_project_id(db, project_key)
    statement = select(Issue).options(*_issue_options()).where(Issue.project_id == project_id)
    if sprint_id is not None:
        statement = statement.where(Issue.sprint_id == sprint_id)
    if status is not None:
        statement = statement.where(Issue.status == status)
    if issue_type is not None:
        statement = statement.where(Issue.issue_type == issue_type)
    if assignee_id is not None:
        statement = statement.where(Issue.assignee_id == assignee_id)
    return list(db.scalars(statement.order_by(Issue.issue_key)))


@router.get("/issues/{issue_key}", response_model=IssueResponse)
def get_issue(issue_key: str, db: Session = Depends(get_db)) -> Issue:
    return _get_issue(db, issue_key)


@router.patch(
    "/issues/{issue_key}/status",
    response_model=IssueStatusTransitionResponse,
    responses={
        400: {"description": "Status is already the requested status"},
        404: {"description": "Issue or employee not found"},
    },
)
def update_issue_status(
    issue_key: str,
    payload: IssueStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> IssueStatusTransitionResponse:
    issue = _get_issue(db, issue_key)
    employee = db.scalar(select(Employee).where(Employee.id == payload.changed_by))
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    old_status = issue.status
    if old_status == payload.new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Status is already {payload.new_status.value}",
        )

    changed_at = datetime.now(timezone.utc)
    issue.status = payload.new_status
    history = IssueHistory(
        issue_id=issue.id,
        old_status=old_status,
        new_status=payload.new_status,
        changed_by=employee.id,
        changed_at=changed_at,
        notes=payload.notes,
    )
    db.add(history)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return IssueStatusTransitionResponse(
        issue_key=issue.issue_key,
        old_status=old_status,
        new_status=payload.new_status,
        changed_by=employee.id,
        changed_at=changed_at,
        notes=payload.notes,
    )


@router.get("/issues/{issue_key}/history", response_model=list[IssueHistoryResponse])
def list_issue_history(
    issue_key: str, db: Session = Depends(get_db)
) -> list[IssueHistory]:
    issue = _get_issue(db, issue_key)
    statement = (
        select(IssueHistory)
        .options(selectinload(IssueHistory.changed_by_employee))
        .where(IssueHistory.issue_id == issue.id)
        .order_by(IssueHistory.changed_at)
    )
    return list(db.scalars(statement))


@router.get("/issues/{issue_key}/comments", response_model=list[CommentResponse])
def list_issue_comments(issue_key: str, db: Session = Depends(get_db)) -> list[Comment]:
    issue = _get_issue(db, issue_key)
    statement = (
        select(Comment)
        .options(selectinload(Comment.employee))
        .where(Comment.issue_id == issue.id)
        .order_by(Comment.created_at)
    )
    return list(db.scalars(statement))


@router.get("/issues/{issue_key}/tests", response_model=list[TestResultResponse])
def list_issue_tests(
    issue_key: str, db: Session = Depends(get_db)
) -> list[TestResult]:
    issue = _get_issue(db, issue_key)
    statement = (
        select(TestResult)
        .options(selectinload(TestResult.tested_by_employee))
        .where(TestResult.issue_id == issue.id)
        .order_by(TestResult.tested_at.asc().nulls_last())
    )
    return list(db.scalars(statement))


@router.get("/issues/{issue_key}/deployments", response_model=list[DeploymentResponse])
def list_issue_deployments(
    issue_key: str, db: Session = Depends(get_db)
) -> list[Deployment]:
    issue = _get_issue(db, issue_key)
    statement = (
        select(Deployment)
        .where(Deployment.issue_id == issue.id)
        .order_by(Deployment.deployment_date.asc().nulls_last())
    )
    return list(db.scalars(statement))
