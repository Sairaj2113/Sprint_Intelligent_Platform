from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.issue import IssuePriority, IssueStatus, IssueType
from app.schemas.employee import EmployeeNameSummary, EmployeeSummary
from app.schemas.sprint import SprintSummary


class ParentIssueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_key: str
    title: str


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_key: str
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None
    assignee_id: uuid.UUID | None
    reporter_id: uuid.UUID | None
    parent_issue_id: uuid.UUID | None
    issue_type: IssueType
    title: str
    description: str | None
    priority: IssuePriority
    story_points: int | None
    status: IssueStatus
    acceptance_criteria: str | None
    technical_notes: str | None
    start_date: datetime.date | None
    due_date: datetime.date | None
    assignee: EmployeeSummary | None = None
    reporter: EmployeeNameSummary | None = None
    parent_issue: ParentIssueSummary | None = None
    sprint: SprintSummary | None = None


class IssueStatusUpdateRequest(BaseModel):
    new_status: IssueStatus
    changed_by: uuid.UUID
    notes: str | None = None


class IssueStatusTransitionResponse(BaseModel):
    issue_key: str
    old_status: IssueStatus
    new_status: IssueStatus
    changed_by: uuid.UUID
    changed_at: datetime.datetime
    notes: str | None
