from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.models.issue import IssueStatus, IssueType


class EmployeeContributionSummary(BaseModel):
    employee_id: uuid.UUID
    assigned_issues: int
    completed_issues: int
    assigned_story_points: int
    completed_story_points: int
    assigned_bugs: int
    resolved_bugs: int
    issues_reaching_testing: int
    issues_deployed: int
    issues_commented_on: int
    reopen_count: int
    average_cycle_time_hours: float | None
    average_development_time_hours: float | None
    average_review_time_hours: float | None
    average_testing_time_hours: float | None


class EmployeeIssueEvidence(BaseModel):
    issue_id: uuid.UUID
    issue_key: str
    title: str
    issue_type: IssueType
    status: IssueStatus
    story_points: int | None
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    was_completed: bool
    reached_testing: bool
    was_deployed: bool
    reopen_count: int
    cycle_time_hours: float | None
    development_time_hours: float | None
    review_time_hours: float | None
    testing_time_hours: float | None
    test_result_count: int
    deployment_count: int
    comment_count: int


class EmployeeContributionEvidence(BaseModel):
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    project_id: uuid.UUID
    project_key: str
    project_name: str
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    summary: EmployeeContributionSummary
    issues: list[EmployeeIssueEvidence]
