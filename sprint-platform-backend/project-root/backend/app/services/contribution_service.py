"""Factual, traceable contribution evidence derived from loaded records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from uuid import UUID

from app.models.comment import Comment
from app.models.deployment import Deployment
from app.models.employee import Employee
from app.models.issue import Issue, IssueStatus
from app.models.issue_history import IssueHistory
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.test_result import TestResult
from app.schemas.contribution import (
    EmployeeContributionEvidence,
    EmployeeContributionSummary,
    EmployeeIssueEvidence,
)
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_employee_contribution_metrics,
    calculate_issue_duration_metrics,
)


def _comments_by_issue(comments: Iterable[Comment]) -> dict[UUID, list[Comment]]:
    grouped: dict[UUID, list[Comment]] = defaultdict(list)
    for comment in comments:
        grouped[comment.issue_id].append(comment)
    return grouped


def build_employee_contribution_evidence(
    employee: Employee,
    project: Project,
    issues: Iterable[Issue],
    histories_by_issue: Mapping[UUID, Sequence[IssueHistory]],
    tests_by_issue: Mapping[UUID, Sequence[TestResult]],
    deployments_by_issue: Mapping[UUID, Sequence[Deployment]],
    comments: Iterable[Comment],
    *,
    sprint: Sprint | None = None,
    sprint_names_by_id: Mapping[UUID, str] | None = None,
) -> EmployeeContributionEvidence:
    """Build assignment-based evidence without querying the database or scoring employees."""
    scoped_issues = list(issues)
    if sprint is not None:
        scoped_issues = [issue for issue in scoped_issues if issue.sprint_id == sprint.id]

    scoped_issue_ids = {issue.id for issue in scoped_issues}
    comment_list = list(comments)
    comments_by_issue = _comments_by_issue(comment_list)
    employee_metrics = calculate_employee_contribution_metrics(employee.id, scoped_issues)
    assigned_issues = [issue for issue in scoped_issues if issue.assignee_id == employee.id]
    issue_evidence: list[EmployeeIssueEvidence] = []
    duration_metrics = []

    for issue in assigned_issues:
        history = histories_by_issue.get(issue.id, [])
        durations = calculate_issue_duration_metrics(history)
        duration_metrics.append(durations)
        reached_testing = any(entry.new_status == IssueStatus.TESTING for entry in history)
        test_results = tests_by_issue.get(issue.id, [])
        deployments = deployments_by_issue.get(issue.id, [])
        sprint_name = (
            sprint_names_by_id.get(issue.sprint_id)
            if sprint_names_by_id is not None and issue.sprint_id is not None
            else sprint.name if sprint is not None and issue.sprint_id == sprint.id else None
        )
        issue_evidence.append(
            EmployeeIssueEvidence(
                issue_id=issue.id,
                issue_key=issue.issue_key,
                title=issue.title,
                issue_type=issue.issue_type,
                status=issue.status,
                story_points=issue.story_points,
                sprint_id=issue.sprint_id,
                sprint_name=sprint_name,
                was_completed=issue.status == IssueStatus.DONE,
                reached_testing=reached_testing,
                was_deployed=bool(deployments),
                reopen_count=durations.reopen_count,
                cycle_time_hours=durations.cycle_time_hours,
                development_time_hours=durations.development_time_hours,
                review_time_hours=durations.review_time_hours,
                testing_time_hours=durations.testing_time_hours,
                test_result_count=len(test_results),
                deployment_count=len(deployments),
                comment_count=len(comments_by_issue.get(issue.id, [])),
            )
        )

    aggregate_durations = calculate_aggregate_duration_metrics(duration_metrics)
    issues_commented_on = len(
        {
            comment.issue_id
            for comment in comment_list
            if comment.employee_id == employee.id and comment.issue_id in scoped_issue_ids
        }
    )
    summary = EmployeeContributionSummary(
        employee_id=employee.id,
        assigned_issues=employee_metrics.assigned_issues,
        completed_issues=employee_metrics.completed_issues,
        assigned_story_points=employee_metrics.assigned_story_points,
        completed_story_points=employee_metrics.completed_story_points,
        assigned_bugs=employee_metrics.assigned_bugs,
        resolved_bugs=employee_metrics.resolved_bugs,
        issues_reaching_testing=sum(evidence.reached_testing for evidence in issue_evidence),
        issues_deployed=sum(evidence.was_deployed for evidence in issue_evidence),
        issues_commented_on=issues_commented_on,
        reopen_count=sum(evidence.reopen_count for evidence in issue_evidence),
        average_cycle_time_hours=aggregate_durations.average_cycle_time_hours,
        average_development_time_hours=aggregate_durations.average_development_time_hours,
        average_review_time_hours=aggregate_durations.average_review_time_hours,
        average_testing_time_hours=aggregate_durations.average_testing_time_hours,
    )
    return EmployeeContributionEvidence(
        employee_id=employee.id,
        employee_code=employee.employee_code,
        employee_name=employee.name,
        project_id=project.id,
        project_key=project.project_key,
        project_name=project.name,
        sprint_id=sprint.id if sprint is not None else None,
        sprint_name=sprint.name if sprint is not None else None,
        summary=summary,
        issues=issue_evidence,
    )
