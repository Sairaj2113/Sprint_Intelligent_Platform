from __future__ import annotations

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.issue import IssueStatus, IssueType
from app.models.sprint import SprintStatus


class DeliveryStage(str, enum.Enum):
    TODO = "TODO"
    DEVELOPMENT = "DEVELOPMENT"
    REVIEW = "REVIEW"
    TESTING = "TESTING"
    DONE_NOT_DEPLOYED = "DONE_NOT_DEPLOYED"
    DEPLOYED = "DEPLOYED"


class WorkflowTransitionSummary(BaseModel):
    old_status: IssueStatus | None
    new_status: IssueStatus
    changed_at: datetime


class IssueWorkflowEvidence(BaseModel):
    issue_id: uuid.UUID
    issue_key: str
    title: str
    issue_type: IssueType
    status: IssueStatus
    story_points: int | None
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    transition_count: int
    reopen_count: int
    reached_in_progress: bool
    reached_code_review: bool
    reached_testing: bool
    reached_done: bool
    blocked_time_hours: float | None
    cycle_time_hours: float | None
    development_time_hours: float | None
    review_time_hours: float | None
    testing_time_hours: float | None
    test_result_count: int
    passed_test_count: int
    failed_test_count: int
    deployment_count: int
    was_deployed: bool
    delivery_stage: DeliveryStage
    transitions: list[WorkflowTransitionSummary]


class WorkflowEvidenceSummary(BaseModel):
    total_issues: int
    issues_in_todo: int
    issues_in_development: int
    issues_in_review: int
    issues_in_testing: int
    issues_done_not_deployed: int
    issues_deployed: int
    reopened_issues: int
    total_reopen_count: int
    issues_reaching_testing: int
    issues_with_test_evidence: int
    issues_with_failed_test_evidence: int
    issues_with_deployment_evidence: int
    average_cycle_time_hours: float | None
    average_development_time_hours: float | None
    average_review_time_hours: float | None
    average_testing_time_hours: float | None
    average_blocked_time_hours: float | None


class ProjectWorkflowEvidenceResponse(BaseModel):
    project_id: uuid.UUID
    project_key: str
    project_name: str
    summary: WorkflowEvidenceSummary
    issues: list[IssueWorkflowEvidence]


class SprintWorkflowEvidenceResponse(BaseModel):
    project_id: uuid.UUID
    project_key: str
    project_name: str
    sprint_id: uuid.UUID
    sprint_name: str
    sprint_status: SprintStatus
    summary: WorkflowEvidenceSummary
    issues: list[IssueWorkflowEvidence]
