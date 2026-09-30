"""Pure, assignment-scoped employee delivery-report calculations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from uuid import UUID

from app.models.comment import Comment
from app.models.deployment import Deployment, DeploymentStatus
from app.models.employee import Employee
from app.models.issue import Issue, IssueStatus, IssueType
from app.models.issue_history import IssueHistory
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.requirement_trace_link import RequirementTraceLink, RequirementTraceLinkKind
from app.models.sprint import Sprint
from app.models.test_result import TestResult
from app.schemas.employee_performance import (
    EmployeeDeliveryMetrics,
    EmployeeDeploymentMetrics,
    EmployeeDocumentedActivityMetrics,
    EmployeeIssueStatusDistribution,
    EmployeeLifecycleTimingMetrics,
    EmployeePerformanceEmployee,
    EmployeePerformanceProject,
    EmployeePerformanceReport,
    EmployeePerformanceScope,
    EmployeeQualityMetrics,
    EmployeeRequirementConnectionMetrics,
)
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_employee_contribution_metrics,
    calculate_issue_duration_metrics,
)


class EmployeePerformanceService:
    """Pure façade for deterministic employee delivery-report calculations."""

    @staticmethod
    def build_report(
        employee: Employee,
        project: Project,
        issues: Iterable[Issue],
        histories_by_issue: Mapping[UUID, Sequence[IssueHistory]],
        tests_by_issue: Mapping[UUID, Sequence[TestResult]],
        deployments_by_issue: Mapping[UUID, Sequence[Deployment]],
        comments: Iterable[Comment],
        requirement_trace_links: Iterable[RequirementTraceLink],
        requirements_by_id: Mapping[UUID, Requirement],
        *,
        sprint: Sprint | None = None,
    ) -> EmployeePerformanceReport:
        return build_employee_performance_report(
            employee,
            project,
            issues,
            histories_by_issue,
            tests_by_issue,
            deployments_by_issue,
            comments,
            requirement_trace_links,
            requirements_by_id,
            sprint=sprint,
        )


def build_employee_performance_report(
    employee: Employee,
    project: Project,
    issues: Iterable[Issue],
    histories_by_issue: Mapping[UUID, Sequence[IssueHistory]],
    tests_by_issue: Mapping[UUID, Sequence[TestResult]],
    deployments_by_issue: Mapping[UUID, Sequence[Deployment]],
    comments: Iterable[Comment],
    requirement_trace_links: Iterable[RequirementTraceLink],
    requirements_by_id: Mapping[UUID, Requirement],
    *,
    sprint: Sprint | None = None,
) -> EmployeePerformanceReport:
    """Build factual metrics without database access, scoring, or inference."""
    scoped_issues = list(issues)
    if sprint is not None:
        scoped_issues = [issue for issue in scoped_issues if issue.sprint_id == sprint.id]
    assigned_issues = [issue for issue in scoped_issues if issue.assignee_id == employee.id]
    assigned_issue_ids = {issue.id for issue in assigned_issues}
    contribution = calculate_employee_contribution_metrics(employee.id, scoped_issues)
    completed_issues = [issue for issue in assigned_issues if issue.status == IssueStatus.DONE]

    status_counts = Counter(issue.status for issue in assigned_issues)
    status_distribution = EmployeeIssueStatusDistribution(
        backlog=status_counts[IssueStatus.BACKLOG],
        selected_for_sprint=status_counts[IssueStatus.SELECTED_FOR_SPRINT],
        todo=status_counts[IssueStatus.TODO],
        in_progress=status_counts[IssueStatus.IN_PROGRESS],
        code_review=status_counts[IssueStatus.CODE_REVIEW],
        testing=status_counts[IssueStatus.TESTING],
        ready_for_release=status_counts[IssueStatus.READY_FOR_RELEASE],
        done=status_counts[IssueStatus.DONE],
    )

    issue_durations = [
        calculate_issue_duration_metrics(histories_by_issue.get(issue.id, ()))
        for issue in assigned_issues
    ]
    aggregate_durations = calculate_aggregate_duration_metrics(issue_durations)
    delivery = EmployeeDeliveryMetrics(
        assigned_issue_count=contribution.assigned_issues,
        completed_issue_count=contribution.completed_issues,
        completion_rate_percentage=(
            contribution.completed_issues / contribution.assigned_issues * 100
            if contribution.assigned_issues
            else None
        ),
        completion_rate_eligible_issue_count=contribution.assigned_issues,
        status_distribution=status_distribution,
        assigned_story_points=contribution.assigned_story_points,
        completed_story_points=contribution.completed_story_points,
        assigned_bug_count=contribution.assigned_bugs,
        resolved_bug_count=contribution.resolved_bugs,
        reopened_assigned_issue_count=sum(item.reopen_count > 0 for item in issue_durations),
        total_reopen_count=sum(item.reopen_count for item in issue_durations),
    )

    linked_tests = [test for issue_id in assigned_issue_ids for test in tests_by_issue.get(issue_id, ())]
    valid_case_tests = [
        test
        for test in linked_tests
        if test.test_cases_total is not None
        and test.test_cases_total > 0
        and test.test_cases_passed is not None
        and 0 <= test.test_cases_passed <= test.test_cases_total
    ]
    total_cases = sum(test.test_cases_total for test in valid_case_tests if test.test_cases_total is not None)
    passed_cases = sum(test.test_cases_passed for test in valid_case_tests if test.test_cases_passed is not None)
    quality = EmployeeQualityMetrics(
        completed_assigned_issue_count=len(completed_issues),
        completed_issues_with_test_evidence=sum(
            bool(tests_by_issue.get(issue.id, ())) for issue in completed_issues
        ),
        completed_issues_without_test_evidence=sum(
            not tests_by_issue.get(issue.id, ()) for issue in completed_issues
        ),
        linked_test_result_count=len(linked_tests),
        test_records_with_valid_case_counts=len(valid_case_tests),
        test_cases_total=total_cases,
        test_cases_passed=passed_cases,
        test_cases_failed=total_cases - passed_cases,
        test_case_pass_rate_percentage=(passed_cases / total_cases * 100 if total_cases else None),
        test_case_pass_rate_eligible_record_count=len(valid_case_tests),
    )

    linked_deployments = [
        deployment
        for issue_id in assigned_issue_ids
        for deployment in deployments_by_issue.get(issue_id, ())
    ]
    deployment_statuses = Counter(deployment.deployment_status for deployment in linked_deployments)
    environment_counts = Counter(
        deployment.environment for deployment in linked_deployments if deployment.environment is not None
    )
    deployment_evidence = EmployeeDeploymentMetrics(
        assigned_issues_with_deployment_evidence=sum(
            bool(deployments_by_issue.get(issue.id, ())) for issue in assigned_issues
        ),
        deployment_record_count=len(linked_deployments),
        not_deployed_count=deployment_statuses[DeploymentStatus.NOT_DEPLOYED],
        staging_count=deployment_statuses[DeploymentStatus.STAGING],
        production_count=deployment_statuses[DeploymentStatus.PRODUCTION],
        failed_count=deployment_statuses[DeploymentStatus.FAILED],
        environment_counts=dict(sorted(environment_counts.items())),
        deployments_without_recorded_environment=sum(
            deployment.environment is None for deployment in linked_deployments
        ),
    )

    requirement_keys: set[str] = set()
    implemented_link_count = 0
    for link in requirement_trace_links:
        if (
            link.link_kind == RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE
            and link.issue_id in assigned_issue_ids
            and link.requirement_id in requirements_by_id
        ):
            implemented_link_count += 1
            requirement_keys.add(requirements_by_id[link.requirement_id].requirement_key)
    requirement_connections = EmployeeRequirementConnectionMetrics(
        explicit_implemented_requirement_keys=sorted(requirement_keys),
        explicit_implemented_requirement_link_count=implemented_link_count,
    )

    authored_comments = [
        comment
        for comment in comments
        if comment.employee_id == employee.id and comment.issue_id in {issue.id for issue in scoped_issues}
    ]
    documented_activity = EmployeeDocumentedActivityMetrics(
        authored_comment_count=len(authored_comments),
        issues_commented_on_count=len({comment.issue_id for comment in authored_comments}),
    )

    lifecycle_timing = EmployeeLifecycleTimingMetrics(
        cycle_time_eligible_issue_count=sum(item.cycle_time_hours is not None for item in issue_durations),
        average_cycle_time_hours=aggregate_durations.average_cycle_time_hours,
        development_time_eligible_issue_count=sum(
            item.development_time_hours is not None for item in issue_durations
        ),
        average_development_time_hours=aggregate_durations.average_development_time_hours,
        review_time_eligible_issue_count=sum(item.review_time_hours is not None for item in issue_durations),
        average_review_time_hours=aggregate_durations.average_review_time_hours,
        testing_time_eligible_issue_count=sum(item.testing_time_hours is not None for item in issue_durations),
        average_testing_time_hours=aggregate_durations.average_testing_time_hours,
    )

    return EmployeePerformanceReport(
        employee=EmployeePerformanceEmployee(
            id=employee.id,
            employee_code=employee.employee_code,
            name=employee.name,
            role=employee.role,
            department=employee.department,
        ),
        project=EmployeePerformanceProject(
            id=project.id,
            project_key=project.project_key,
            name=project.name,
        ),
        scope=_scope(sprint),
        delivery=delivery,
        quality=quality,
        deployment_evidence=deployment_evidence,
        requirement_connections=requirement_connections,
        documented_activity=documented_activity,
        lifecycle_timing=lifecycle_timing,
        limitations=_limitations(
            assigned_issue_count=len(assigned_issues),
            valid_test_case_count=len(valid_case_tests),
        ),
    )


def _scope(sprint: Sprint | None) -> EmployeePerformanceScope:
    if sprint is None:
        return EmployeePerformanceScope(
            kind="PROJECT",
            sprint_id=None,
            sprint_name=None,
            definition="Issues currently associated with the project and currently assigned to the employee.",
        )
    return EmployeePerformanceScope(
        kind="SPRINT",
        sprint_id=sprint.id,
        sprint_name=sprint.name,
        definition=(
            "Issues currently associated with the selected sprint and currently assigned "
            "to the employee; this is not historical sprint-assignment evidence."
        ),
    )


def _limitations(*, assigned_issue_count: int, valid_test_case_count: int) -> list[str]:
    limitations = [
        "Issue assignment records assignment, not sole implementation or employee effort.",
        "Story points are estimates, not direct measures of effort or productivity.",
        "Test evidence linked to an assigned issue does not establish that the employee performed testing.",
        "Deployment evidence linked to an assigned issue does not establish that the employee performed deployment.",
        "Lifecycle durations describe issue status history, not time worked by the employee.",
        "Requirement connections include only explicit IMPLEMENTED_BY_ISSUE links and do not establish requirement ownership or complete implementation.",
        "Missing evidence is not evidence of poor performance.",
    ]
    if assigned_issue_count == 0:
        limitations.append(
            "No issues are currently assigned in the selected scope; percentage metrics are unavailable."
        )
    if valid_test_case_count == 0:
        limitations.append(
            "No linked test records have valid test-case totals and pass counts; the test-case pass rate is unavailable."
        )
    return limitations
