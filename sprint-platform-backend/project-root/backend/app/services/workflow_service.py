"""Pure workflow and delivery evidence calculations from already-loaded records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from uuid import UUID

from app.models.deployment import Deployment
from app.models.issue import Issue, IssueStatus
from app.models.issue_history import IssueHistory
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.test_result import TestResult, TestingStatus
from app.schemas.kpi import IssueDurationMetrics
from app.schemas.workflow import (
    DeliveryStage,
    IssueWorkflowEvidence,
    ProjectWorkflowEvidenceResponse,
    SprintWorkflowEvidenceResponse,
    WorkflowEvidenceSummary,
    WorkflowTransitionSummary,
)
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_issue_duration_metrics,
)


def _delivery_stage(issue: Issue, deployments: Sequence[Deployment]) -> DeliveryStage:
    if deployments:
        return DeliveryStage.DEPLOYED
    if issue.status == IssueStatus.DONE:
        return DeliveryStage.DONE_NOT_DEPLOYED
    if issue.status == IssueStatus.TESTING:
        return DeliveryStage.TESTING
    if issue.status == IssueStatus.CODE_REVIEW:
        return DeliveryStage.REVIEW
    if issue.status == IssueStatus.IN_PROGRESS:
        return DeliveryStage.DEVELOPMENT
    return DeliveryStage.TODO


def _reached(history: Sequence[IssueHistory], current_status: IssueStatus, target: IssueStatus) -> bool:
    return current_status == target or any(entry.new_status == target for entry in history)


def _build_issue_evidence(
    issue: Issue,
    history: Sequence[IssueHistory],
    test_results: Sequence[TestResult],
    deployments: Sequence[Deployment],
    sprint_name: str | None,
) -> IssueWorkflowEvidence:
    ordered_history = sorted(history, key=lambda entry: entry.changed_at)
    durations = calculate_issue_duration_metrics(ordered_history)
    passed_test_count = sum(test.testing_status == TestingStatus.PASSED for test in test_results)
    failed_test_count = sum(test.testing_status == TestingStatus.FAILED for test in test_results)
    transitions = [
        WorkflowTransitionSummary(
            old_status=entry.old_status,
            new_status=entry.new_status,
            changed_at=entry.changed_at,
        )
        for entry in ordered_history
    ]
    return IssueWorkflowEvidence(
        issue_id=issue.id,
        issue_key=issue.issue_key,
        title=issue.title,
        issue_type=issue.issue_type,
        status=issue.status,
        story_points=issue.story_points,
        sprint_id=issue.sprint_id,
        sprint_name=sprint_name,
        transition_count=sum(entry.old_status != entry.new_status for entry in ordered_history),
        reopen_count=durations.reopen_count,
        reached_in_progress=_reached(ordered_history, issue.status, IssueStatus.IN_PROGRESS),
        reached_code_review=_reached(ordered_history, issue.status, IssueStatus.CODE_REVIEW),
        reached_testing=_reached(ordered_history, issue.status, IssueStatus.TESTING),
        reached_done=_reached(ordered_history, issue.status, IssueStatus.DONE),
        # IssueStatus has no BLOCKED value, so a factual duration cannot be reconstructed.
        blocked_time_hours=None,
        cycle_time_hours=durations.cycle_time_hours,
        development_time_hours=durations.development_time_hours,
        review_time_hours=durations.review_time_hours,
        testing_time_hours=durations.testing_time_hours,
        test_result_count=len(test_results),
        passed_test_count=passed_test_count,
        failed_test_count=failed_test_count,
        deployment_count=len(deployments),
        was_deployed=bool(deployments),
        delivery_stage=_delivery_stage(issue, deployments),
        transitions=transitions,
    )


def _build_summary(evidence: Sequence[IssueWorkflowEvidence]) -> WorkflowEvidenceSummary:
    durations = calculate_aggregate_duration_metrics(
        [
            IssueDurationMetrics(
                cycle_time_hours=item.cycle_time_hours,
                development_time_hours=item.development_time_hours,
                review_time_hours=item.review_time_hours,
                testing_time_hours=item.testing_time_hours,
                reopen_count=item.reopen_count,
            )
            for item in evidence
        ]
    )
    return WorkflowEvidenceSummary(
        total_issues=len(evidence),
        issues_in_todo=sum(item.delivery_stage == DeliveryStage.TODO for item in evidence),
        issues_in_development=sum(item.delivery_stage == DeliveryStage.DEVELOPMENT for item in evidence),
        issues_in_review=sum(item.delivery_stage == DeliveryStage.REVIEW for item in evidence),
        issues_in_testing=sum(item.delivery_stage == DeliveryStage.TESTING for item in evidence),
        issues_done_not_deployed=sum(
            item.delivery_stage == DeliveryStage.DONE_NOT_DEPLOYED for item in evidence
        ),
        issues_deployed=sum(item.delivery_stage == DeliveryStage.DEPLOYED for item in evidence),
        reopened_issues=sum(item.reopen_count > 0 for item in evidence),
        total_reopen_count=sum(item.reopen_count for item in evidence),
        issues_reaching_testing=sum(item.reached_testing for item in evidence),
        issues_with_test_evidence=sum(item.test_result_count > 0 for item in evidence),
        issues_with_failed_test_evidence=sum(item.failed_test_count > 0 for item in evidence),
        issues_with_deployment_evidence=sum(item.was_deployed for item in evidence),
        average_cycle_time_hours=durations.average_cycle_time_hours,
        average_development_time_hours=durations.average_development_time_hours,
        average_review_time_hours=durations.average_review_time_hours,
        average_testing_time_hours=durations.average_testing_time_hours,
        average_blocked_time_hours=None,
    )


def build_workflow_evidence(
    project: Project,
    issues: Iterable[Issue],
    histories_by_issue: Mapping[UUID, Sequence[IssueHistory]],
    tests_by_issue: Mapping[UUID, Sequence[TestResult]],
    deployments_by_issue: Mapping[UUID, Sequence[Deployment]],
    *,
    sprint: Sprint | None = None,
    sprint_names_by_id: Mapping[UUID, str] | None = None,
) -> ProjectWorkflowEvidenceResponse | SprintWorkflowEvidenceResponse:
    """Build project-wide or sprint-specific factual workflow evidence without database queries."""
    scoped_issues = list(issues)
    if sprint is not None:
        scoped_issues = [issue for issue in scoped_issues if issue.sprint_id == sprint.id]

    issue_evidence = [
        _build_issue_evidence(
            issue,
            histories_by_issue.get(issue.id, []),
            tests_by_issue.get(issue.id, []),
            deployments_by_issue.get(issue.id, []),
            sprint_names_by_id.get(issue.sprint_id)
            if sprint_names_by_id is not None and issue.sprint_id is not None
            else sprint.name if sprint is not None and issue.sprint_id == sprint.id else None,
        )
        for issue in scoped_issues
    ]
    summary = _build_summary(issue_evidence)
    if sprint is not None:
        return SprintWorkflowEvidenceResponse(
            project_id=project.id,
            project_key=project.project_key,
            project_name=project.name,
            sprint_id=sprint.id,
            sprint_name=sprint.name,
            sprint_status=sprint.status,
            summary=summary,
            issues=issue_evidence,
        )
    return ProjectWorkflowEvidenceResponse(
        project_id=project.id,
        project_key=project.project_key,
        project_name=project.name,
        summary=summary,
        issues=issue_evidence,
    )
