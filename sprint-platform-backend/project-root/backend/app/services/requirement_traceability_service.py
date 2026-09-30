"""Curated, project-scoped requirement traceability without semantic inference."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Deployment,
    DocumentChunk,
    DocumentStatus,
    Employee,
    Issue,
    Project,
    ProjectMember,
    Requirement,
    RequirementTraceLink,
    TestResult,
)
from app.models.requirement_trace_link import RequirementTraceLinkKind


class RequirementTraceabilityError(Exception):
    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise RequirementTraceabilityError("Project not found", status_code=404)
    return project


def _member_employee(db: Session, project: Project, employee_id: uuid.UUID, *, role: str) -> Employee:
    employee = db.scalar(select(Employee).where(Employee.id == employee_id))
    if employee is None:
        raise RequirementTraceabilityError(f"{role} not found", status_code=404)
    is_member = db.scalar(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project.id,
            ProjectMember.employee_id == employee.id,
        )
    )
    if is_member is None:
        raise RequirementTraceabilityError(f"{role} must be a project member")
    return employee


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _get_requirement(db: Session, project: Project, requirement_key: str) -> Requirement:
    requirement = db.scalar(
        select(Requirement).where(
            Requirement.project_id == project.id,
            Requirement.requirement_key == requirement_key,
        )
    )
    if requirement is None:
        raise RequirementTraceabilityError("Requirement not found", status_code=404)
    return requirement


def create_requirement(
    db: Session,
    project_key: str,
    *,
    requirement_key: str,
    statement: str,
    source_chunk_id: uuid.UUID,
    recorded_by_id: uuid.UUID,
) -> Requirement:
    project = _project(db, project_key)
    normalized_key = requirement_key.strip()
    normalized_statement = statement.strip()
    if not normalized_key or not normalized_statement:
        raise RequirementTraceabilityError("Requirement key and statement must not be blank")
    if db.scalar(select(Requirement.id).where(Requirement.project_id == project.id, Requirement.requirement_key == normalized_key)) is not None:
        raise RequirementTraceabilityError("Requirement key already exists", status_code=409)
    chunk = db.scalar(
        select(DocumentChunk)
        .join(DocumentChunk.document)
        .where(DocumentChunk.id == source_chunk_id, DocumentChunk.project_id == project.id)
    )
    if chunk is None:
        raise RequirementTraceabilityError("Source document chunk not found", status_code=404)
    if chunk.document.status is not DocumentStatus.PROCESSED:
        raise RequirementTraceabilityError("Source document must be processed")
    if _normalized(normalized_statement) not in _normalized(chunk.content):
        raise RequirementTraceabilityError("Requirement statement must occur in the canonical source chunk")
    _member_employee(db, project, recorded_by_id, role="Requirement recorder")
    requirement = Requirement(
        project_id=project.id,
        requirement_key=normalized_key,
        statement=normalized_statement,
        source_chunk_id=chunk.id,
        recorded_by_id=recorded_by_id,
    )
    db.add(requirement)
    return requirement


def create_verified_trace_link(
    db: Session,
    project_key: str,
    requirement_key: str,
    *,
    link_kind: RequirementTraceLinkKind,
    issue_id: uuid.UUID | None,
    test_result_id: uuid.UUID | None,
    deployment_id: uuid.UUID | None,
    verified_by_id: uuid.UUID,
    notes: str | None = None,
) -> RequirementTraceLink:
    project = _project(db, project_key)
    requirement = _get_requirement(db, project, requirement_key)
    _member_employee(db, project, verified_by_id, role="Trace-link verifier")
    targets = (issue_id, test_result_id, deployment_id)
    if sum(value is not None for value in targets) != 1:
        raise RequirementTraceabilityError("Exactly one trace-link target is required")

    target_kwargs: dict[str, uuid.UUID] = {}
    if link_kind is RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE:
        if issue_id is None:
            raise RequirementTraceabilityError("Trace-link target does not match link_kind")
        if db.scalar(select(Issue.id).where(Issue.id == issue_id, Issue.project_id == project.id)) is None:
            raise RequirementTraceabilityError("Issue target not found", status_code=404)
        target_kwargs["issue_id"] = issue_id
    elif link_kind is RequirementTraceLinkKind.VERIFIED_BY_TEST:
        if test_result_id is None:
            raise RequirementTraceabilityError("Trace-link target does not match link_kind")
        test = db.scalar(select(TestResult).where(TestResult.id == test_result_id))
        if test is None or db.scalar(select(Issue.id).where(Issue.id == test.issue_id, Issue.project_id == project.id)) is None:
            raise RequirementTraceabilityError("Test-result target not found", status_code=404)
        target_kwargs["test_result_id"] = test_result_id
    else:
        if deployment_id is None:
            raise RequirementTraceabilityError("Trace-link target does not match link_kind")
        deployment = db.scalar(select(Deployment).where(Deployment.id == deployment_id))
        if deployment is None or db.scalar(select(Issue.id).where(Issue.id == deployment.issue_id, Issue.project_id == project.id)) is None:
            raise RequirementTraceabilityError("Deployment target not found", status_code=404)
        target_kwargs["deployment_id"] = deployment_id

    existing = db.scalar(
        select(RequirementTraceLink.id).where(
            RequirementTraceLink.requirement_id == requirement.id,
            RequirementTraceLink.link_kind == link_kind,
            *[getattr(RequirementTraceLink, key) == value for key, value in target_kwargs.items()],
        )
    )
    if existing is not None:
        raise RequirementTraceabilityError("Verified trace link already exists", status_code=409)
    link = RequirementTraceLink(
        project_id=project.id,
        requirement_id=requirement.id,
        link_kind=link_kind,
        verified_by_id=verified_by_id,
        notes=notes.strip() if isinstance(notes, str) and notes.strip() else None,
        **target_kwargs,
    )
    db.add(link)
    return link


def list_requirements(db: Session, project_key: str) -> list[Requirement]:
    project = _project(db, project_key)
    return list(db.scalars(select(Requirement).where(Requirement.project_id == project.id).order_by(Requirement.requirement_key, Requirement.id)))


def get_requirement(db: Session, project_key: str, requirement_key: str) -> Requirement:
    return _get_requirement(db, _project(db, project_key), requirement_key)


def list_trace_links(db: Session, project_key: str, requirement_key: str) -> list[RequirementTraceLink]:
    requirement = _get_requirement(db, _project(db, project_key), requirement_key)
    return list(db.scalars(select(RequirementTraceLink).where(RequirementTraceLink.requirement_id == requirement.id).order_by(RequirementTraceLink.link_kind, RequirementTraceLink.id)))
