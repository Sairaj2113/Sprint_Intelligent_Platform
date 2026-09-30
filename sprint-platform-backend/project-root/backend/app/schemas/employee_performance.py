"""Read-only, deterministic employee delivery-report contracts."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class EmployeePerformanceEmployee(BaseModel):
    id: uuid.UUID
    employee_code: str
    name: str
    role: str | None
    department: str | None


class EmployeePerformanceProject(BaseModel):
    id: uuid.UUID
    project_key: str
    name: str


class EmployeePerformanceScope(BaseModel):
    kind: str
    sprint_id: uuid.UUID | None
    sprint_name: str | None
    definition: str


class EmployeeIssueStatusDistribution(BaseModel):
    backlog: int
    selected_for_sprint: int
    todo: int
    in_progress: int
    code_review: int
    testing: int
    ready_for_release: int
    done: int


class EmployeeDeliveryMetrics(BaseModel):
    assigned_issue_count: int
    completed_issue_count: int
    completion_rate_percentage: float | None
    completion_rate_eligible_issue_count: int
    status_distribution: EmployeeIssueStatusDistribution
    assigned_story_points: int
    completed_story_points: int
    assigned_bug_count: int
    resolved_bug_count: int
    reopened_assigned_issue_count: int
    total_reopen_count: int


class EmployeeQualityMetrics(BaseModel):
    completed_assigned_issue_count: int
    completed_issues_with_test_evidence: int
    completed_issues_without_test_evidence: int
    linked_test_result_count: int
    test_records_with_valid_case_counts: int
    test_cases_total: int
    test_cases_passed: int
    test_cases_failed: int
    test_case_pass_rate_percentage: float | None
    test_case_pass_rate_eligible_record_count: int


class EmployeeDeploymentMetrics(BaseModel):
    assigned_issues_with_deployment_evidence: int
    deployment_record_count: int
    not_deployed_count: int
    staging_count: int
    production_count: int
    failed_count: int
    environment_counts: dict[str, int]
    deployments_without_recorded_environment: int


class EmployeeRequirementConnectionMetrics(BaseModel):
    explicit_implemented_requirement_keys: list[str]
    explicit_implemented_requirement_link_count: int


class EmployeeDocumentedActivityMetrics(BaseModel):
    authored_comment_count: int
    issues_commented_on_count: int


class EmployeeLifecycleTimingMetrics(BaseModel):
    cycle_time_eligible_issue_count: int
    average_cycle_time_hours: float | None
    development_time_eligible_issue_count: int
    average_development_time_hours: float | None
    review_time_eligible_issue_count: int
    average_review_time_hours: float | None
    testing_time_eligible_issue_count: int
    average_testing_time_hours: float | None


class EmployeePerformanceReport(BaseModel):
    employee: EmployeePerformanceEmployee
    project: EmployeePerformanceProject
    scope: EmployeePerformanceScope
    delivery: EmployeeDeliveryMetrics
    quality: EmployeeQualityMetrics
    deployment_evidence: EmployeeDeploymentMetrics
    requirement_connections: EmployeeRequirementConnectionMetrics
    documented_activity: EmployeeDocumentedActivityMetrics
    lifecycle_timing: EmployeeLifecycleTimingMetrics
    limitations: list[str]
