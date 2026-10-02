"""Read-only current-assignment employee contribution report contracts."""

from __future__ import annotations

import datetime
import uuid
from enum import Enum

from pydantic import BaseModel

from app.models.document import DocumentType
from app.models.issue import IssueStatus, IssueType
from app.models.requirement_trace_link import RequirementTraceLinkKind
from app.models.test_result import TestingStatus
from app.models.deployment import DeploymentStatus


class ContributionAttributionBasis(str, Enum):
    """The only employee-to-issue attribution basis supported in Phase 14A."""

    CURRENT_ASSIGNMENT = "CURRENT_ASSIGNMENT"


class ContributionLinkBasis(str, Enum):
    """Persisted relationship kinds retained distinctly in the report."""

    LINKED_TO_CURRENTLY_ASSIGNED_ISSUE = "LINKED_TO_CURRENTLY_ASSIGNED_ISSUE"
    EXPLICIT_REQUIREMENT_TRACE = "EXPLICIT_REQUIREMENT_TRACE"
    CANONICAL_REQUIREMENT_SOURCE = "CANONICAL_REQUIREMENT_SOURCE"


class ContributionEmployee(BaseModel):
    id: uuid.UUID
    employee_code: str
    name: str
    role: str | None
    department: str | None


class ContributionProject(BaseModel):
    id: uuid.UUID
    project_key: str
    name: str


class ContributionScope(BaseModel):
    kind: str
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    definition: str


class CurrentSprintContext(BaseModel):
    id: uuid.UUID
    name: str
    status: str


class CurrentlyAssignedIssueContribution(BaseModel):
    issue_id: uuid.UUID
    issue_key: str
    title: str
    issue_type: IssueType
    current_status: IssueStatus
    current_sprint_id: uuid.UUID | None
    current_sprint_name: str | None
    attribution_basis: ContributionAttributionBasis
    is_currently_recorded_done: bool


class AuthoredCommentContribution(BaseModel):
    comment_id: uuid.UUID
    issue_id: uuid.UUID
    issue_key: str
    content: str
    created_at: datetime.datetime


class LinkedTestContribution(BaseModel):
    test_result_id: uuid.UUID
    issue_id: uuid.UUID
    issue_key: str
    link_basis: ContributionLinkBasis
    testing_status: TestingStatus
    test_cases_total: int | None
    test_cases_passed: int | None
    bugs_found: int | None
    reopened_count: int | None
    testing_notes: str | None
    tested_at: datetime.datetime | None


class LinkedDeploymentContribution(BaseModel):
    deployment_id: uuid.UUID
    issue_id: uuid.UUID
    issue_key: str
    link_basis: ContributionLinkBasis
    deployment_status: DeploymentStatus
    environment: str | None
    deployment_date: datetime.datetime | None
    production_notes: str | None
    production_incidents: str | None


class TraceVerificationMetadata(BaseModel):
    verified_by_id: uuid.UUID
    verified_at: datetime.datetime


class ExplicitRequirementConnection(BaseModel):
    requirement_id: uuid.UUID
    requirement_key: str
    requirement_statement: str
    issue_id: uuid.UUID
    issue_key: str
    trace_link_id: uuid.UUID
    trace_link_kind: RequirementTraceLinkKind
    connection_basis: ContributionLinkBasis
    trace_verification: TraceVerificationMetadata


class CanonicalRequirementDocumentContext(BaseModel):
    requirement_id: uuid.UUID
    requirement_key: str
    source_chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    document_type: DocumentType
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    context_basis: ContributionLinkBasis


class ContributionEvidenceCoverage(BaseModel):
    current_assignment_issue_count: int
    current_assignment_issue_records_included: int
    authored_comment_count: int
    linked_test_evidence_count: int
    linked_deployment_evidence_count: int
    explicit_requirement_connection_count: int
    canonical_requirement_document_context_count: int
    count_bounded: bool


class EmployeeContributionReport(BaseModel):
    """A deterministic current-assignment contribution context, not an evaluation."""

    employee: ContributionEmployee
    project: ContributionProject
    scope: ContributionScope
    currently_assigned_issues: list[CurrentlyAssignedIssueContribution]
    currently_assigned_issue_keys_recorded_done: list[str]
    current_sprint_context: list[CurrentSprintContext]
    authored_comments: list[AuthoredCommentContribution]
    linked_test_evidence: list[LinkedTestContribution]
    linked_deployment_evidence: list[LinkedDeploymentContribution]
    explicit_requirement_connections: list[ExplicitRequirementConnection]
    canonical_requirement_document_context: list[CanonicalRequirementDocumentContext]
    evidence_coverage: ContributionEvidenceCoverage
    limitations: list[str]
