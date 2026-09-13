"""Safe API response shapes for factual structured evidence packages."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel

from app.models.deployment import DeploymentStatus
from app.models.issue import IssueStatus, IssueType
from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.schemas.contribution import EmployeeContributionEvidence
from app.schemas.kpi import (
    AggregateDurationMetrics,
    BugMetrics,
    IssueMetrics,
    StatusDistribution,
    StoryPointMetrics,
)
from app.schemas.workflow import ProjectWorkflowEvidenceResponse, SprintWorkflowEvidenceResponse


class StructuredEvidenceRequest(BaseModel):
    employee_reference: str | None = None
    sprint_reference: str | None = None


class StructuredProjectEvidenceRead(BaseModel):
    id: uuid.UUID
    project_key: str
    name: str
    status: ProjectStatus
    methodology: ProjectMethodology | None


class StructuredEmployeeEvidenceRead(BaseModel):
    id: uuid.UUID
    employee_code: str
    name: str
    role: str | None
    department: str | None


class StructuredSprintEvidenceRead(BaseModel):
    id: uuid.UUID
    name: str
    status: SprintStatus
    start_date: datetime.date | None
    end_date: datetime.date | None


class StructuredIssueEvidenceRead(BaseModel):
    id: uuid.UUID
    issue_key: str
    title: str
    issue_type: IssueType
    status: IssueStatus
    story_points: int | None
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    created_at: datetime.datetime
    completed_at: datetime.datetime | None


class StructuredTestEvidenceRead(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    testing_status: TestingStatus
    test_cases_total: int | None
    test_cases_passed: int | None
    bugs_found: int | None
    reopened_count: int | None
    tested_by: uuid.UUID | None
    tested_by_name: str | None
    tested_at: datetime.datetime | None


class StructuredDeploymentEvidenceRead(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    deployment_status: DeploymentStatus
    environment: str | None
    deployment_date: datetime.datetime | None
    production_notes: str | None
    production_incidents: str | None


class StructuredCommentEvidenceRead(BaseModel):
    id: uuid.UUID
    issue_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None
    content: str
    created_at: datetime.datetime


class StructuredKpiEvidenceRead(BaseModel):
    issue_metrics: IssueMetrics
    story_point_metrics: StoryPointMetrics
    bug_metrics: BugMetrics
    status_distribution: StatusDistribution
    duration_metrics: AggregateDurationMetrics


class StructuredEvidenceResponse(BaseModel):
    project: StructuredProjectEvidenceRead
    employee: StructuredEmployeeEvidenceRead | None
    sprint: StructuredSprintEvidenceRead | None
    employee_scope_active: bool
    sprint_scope_active: bool
    issue_scope: str
    issue_count: int
    test_evidence_count: int
    deployment_evidence_count: int
    comment_evidence_count: int
    issues: list[StructuredIssueEvidenceRead]
    tests: list[StructuredTestEvidenceRead]
    deployments: list[StructuredDeploymentEvidenceRead]
    comments: list[StructuredCommentEvidenceRead]
    contribution: EmployeeContributionEvidence | None
    workflow: ProjectWorkflowEvidenceResponse | SprintWorkflowEvidenceResponse
    kpis: StructuredKpiEvidenceRead
    warnings: list[str]
