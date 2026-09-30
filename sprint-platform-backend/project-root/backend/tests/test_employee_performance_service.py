from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.deployment import DeploymentStatus
from app.models.issue import IssueStatus, IssueType
from app.models.requirement_trace_link import RequirementTraceLinkKind
from app.models.test_result import TestingStatus
from app.services.employee_performance_service import (
    EmployeePerformanceService,
    build_employee_performance_report,
)


EMPLOYEE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_EMPLOYEE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SPRINT_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
OTHER_SPRINT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def employee() -> SimpleNamespace:
    return SimpleNamespace(
        id=EMPLOYEE_ID,
        employee_code="EMP001",
        name="Sairaj Pankar",
        role="Engineer",
        department="Engineering",
    )


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="BLI", name="Bank Loan")


def sprint() -> SimpleNamespace:
    return SimpleNamespace(id=SPRINT_ID, name="Sprint One")


def issue(
    number: int,
    status: IssueStatus,
    *,
    assignee_id: uuid.UUID | None = EMPLOYEE_ID,
    issue_type: IssueType = IssueType.TASK,
    story_points: int | None = 3,
    sprint_id: uuid.UUID | None = SPRINT_ID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(int=number),
        issue_key=f"BLI-{number}",
        status=status,
        assignee_id=assignee_id,
        issue_type=issue_type,
        story_points=story_points,
        sprint_id=sprint_id,
    )


def history(old: IssueStatus | None, new: IssueStatus, at: datetime) -> SimpleNamespace:
    return SimpleNamespace(old_status=old, new_status=new, changed_at=at)


def test_result(
    *,
    total: int | None,
    passed: int | None,
    status: TestingStatus = TestingStatus.PASSED,
) -> SimpleNamespace:
    return SimpleNamespace(test_cases_total=total, test_cases_passed=passed, testing_status=status)


def deployment(status: DeploymentStatus, environment: str | None) -> SimpleNamespace:
    return SimpleNamespace(deployment_status=status, environment=environment)


def report(
    issues: list[SimpleNamespace],
    histories: dict[uuid.UUID, list[SimpleNamespace]] | None = None,
    tests: dict[uuid.UUID, list[SimpleNamespace]] | None = None,
    deployments: dict[uuid.UUID, list[SimpleNamespace]] | None = None,
    comments: list[SimpleNamespace] | None = None,
    links: list[SimpleNamespace] | None = None,
    requirements: dict[uuid.UUID, SimpleNamespace] | None = None,
    *,
    selected_sprint: SimpleNamespace | None = None,
):
    return build_employee_performance_report(
        employee(), project(), issues, histories or {}, tests or {}, deployments or {}, comments or [],
        links or [], requirements or {}, sprint=selected_sprint,
    )


class EmployeePerformanceServiceTests(unittest.TestCase):
    def test_service_facade_uses_the_same_pure_report_calculation(self) -> None:
        item = issue(1, IssueStatus.DONE)
        result = EmployeePerformanceService.build_report(
            employee(), project(), [item], {}, {}, {}, [], [], {}
        )

        self.assertEqual(result.delivery.completed_issue_count, 1)

    def test_all_eight_statuses_are_counted_for_assigned_issues_only(self) -> None:
        statuses = list(IssueStatus)
        issues = [issue(index + 1, status) for index, status in enumerate(statuses)]
        issues.append(issue(99, IssueStatus.DONE, assignee_id=OTHER_EMPLOYEE_ID))

        result = report(issues)

        self.assertEqual(result.delivery.assigned_issue_count, 8)
        self.assertEqual(result.delivery.completed_issue_count, 1)
        self.assertEqual(result.delivery.completion_rate_percentage, 12.5)
        self.assertEqual(result.delivery.status_distribution.model_dump(), {
            "backlog": 1, "selected_for_sprint": 1, "todo": 1, "in_progress": 1,
            "code_review": 1, "testing": 1, "ready_for_release": 1, "done": 1,
        })

    def test_zero_assigned_issues_uses_null_percentage_and_limitations(self) -> None:
        result = report([issue(1, IssueStatus.DONE, assignee_id=OTHER_EMPLOYEE_ID)])

        self.assertEqual(result.delivery.assigned_issue_count, 0)
        self.assertIsNone(result.delivery.completion_rate_percentage)
        self.assertIsNone(result.quality.test_case_pass_rate_percentage)
        self.assertTrue(any("percentage metrics are unavailable" in item for item in result.limitations))

    def test_quality_counts_only_valid_case_denominators_and_completed_test_coverage(self) -> None:
        done_with_test = issue(1, IssueStatus.DONE, story_points=5)
        done_without_test = issue(2, IssueStatus.DONE, story_points=None)
        active = issue(3, IssueStatus.IN_PROGRESS, issue_type=IssueType.BUG)
        tests = {
            done_with_test.id: [
                test_result(total=10, passed=8),
                test_result(total=0, passed=0),
                test_result(total=5, passed=6),
            ],
            active.id: [test_result(total=4, passed=4, status=TestingStatus.FAILED)],
        }

        result = report([done_with_test, done_without_test, active], tests=tests)

        self.assertEqual(result.delivery.assigned_story_points, 8)
        self.assertEqual(result.delivery.completed_story_points, 5)
        self.assertEqual(result.delivery.assigned_bug_count, 1)
        self.assertEqual(result.quality.completed_issues_with_test_evidence, 1)
        self.assertEqual(result.quality.completed_issues_without_test_evidence, 1)
        self.assertEqual(result.quality.linked_test_result_count, 4)
        self.assertEqual(result.quality.test_records_with_valid_case_counts, 2)
        self.assertEqual(result.quality.test_cases_total, 14)
        self.assertEqual(result.quality.test_cases_passed, 12)
        self.assertEqual(result.quality.test_cases_failed, 2)
        self.assertAlmostEqual(result.quality.test_case_pass_rate_percentage or 0, 85.714285714)

    def test_deployment_evidence_is_associated_with_assignment_not_personal_deployment(self) -> None:
        assigned = issue(1, IssueStatus.DONE)
        other = issue(2, IssueStatus.DONE, assignee_id=OTHER_EMPLOYEE_ID)
        result = report(
            [assigned, other],
            deployments={
                assigned.id: [
                    deployment(DeploymentStatus.STAGING, "staging"),
                    deployment(DeploymentStatus.PRODUCTION, None),
                ],
                other.id: [deployment(DeploymentStatus.FAILED, "production")],
            },
        )

        self.assertEqual(result.deployment_evidence.assigned_issues_with_deployment_evidence, 1)
        self.assertEqual(result.deployment_evidence.deployment_record_count, 2)
        self.assertEqual(result.deployment_evidence.staging_count, 1)
        self.assertEqual(result.deployment_evidence.production_count, 1)
        self.assertEqual(result.deployment_evidence.failed_count, 0)
        self.assertEqual(result.deployment_evidence.environment_counts, {"staging": 1})
        self.assertEqual(result.deployment_evidence.deployments_without_recorded_environment, 1)
        self.assertTrue(any("does not establish that the employee performed deployment" in item for item in result.limitations))

    def test_comments_are_authorship_and_requirement_connections_are_explicit_issue_links_only(self) -> None:
        assigned = issue(1, IssueStatus.DONE)
        other = issue(2, IssueStatus.DONE, assignee_id=OTHER_EMPLOYEE_ID)
        requirement_id = uuid.UUID(int=500)
        requirements = {requirement_id: SimpleNamespace(requirement_key="BLI-REQ-001")}
        links = [
            SimpleNamespace(
                requirement_id=requirement_id,
                issue_id=assigned.id,
                link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
            ),
            SimpleNamespace(
                requirement_id=requirement_id,
                issue_id=None,
                link_kind=RequirementTraceLinkKind.VERIFIED_BY_TEST,
            ),
            SimpleNamespace(
                requirement_id=requirement_id,
                issue_id=other.id,
                link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
            ),
        ]
        comments = [
            SimpleNamespace(employee_id=EMPLOYEE_ID, issue_id=assigned.id),
            SimpleNamespace(employee_id=EMPLOYEE_ID, issue_id=assigned.id),
            SimpleNamespace(employee_id=EMPLOYEE_ID, issue_id=other.id),
            SimpleNamespace(employee_id=OTHER_EMPLOYEE_ID, issue_id=assigned.id),
        ]

        result = report([assigned, other], comments=comments, links=links, requirements=requirements)

        # Comment authorship is project-scoped activity, independent of issue assignment.
        self.assertEqual(result.documented_activity.authored_comment_count, 3)
        self.assertEqual(result.documented_activity.issues_commented_on_count, 2)
        self.assertEqual(result.requirement_connections.explicit_implemented_requirement_keys, ["BLI-REQ-001"])
        self.assertEqual(result.requirement_connections.explicit_implemented_requirement_link_count, 1)

    def test_lifecycle_metrics_have_eligibility_counts_and_reopens(self) -> None:
        first = issue(1, IssueStatus.DONE)
        second = issue(2, IssueStatus.IN_PROGRESS)
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        histories = {
            first.id: [
                history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
                history(IssueStatus.IN_PROGRESS, IssueStatus.TESTING, start + timedelta(hours=12)),
                history(IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=24)),
                history(IssueStatus.DONE, IssueStatus.TESTING, start + timedelta(hours=30)),
            ],
            second.id: [history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start)],
        }

        result = report([first, second], histories=histories)

        self.assertEqual(result.delivery.reopened_assigned_issue_count, 1)
        self.assertEqual(result.delivery.total_reopen_count, 1)
        self.assertEqual(result.lifecycle_timing.cycle_time_eligible_issue_count, 1)
        self.assertEqual(result.lifecycle_timing.average_cycle_time_hours, 24.0)
        self.assertEqual(result.lifecycle_timing.development_time_eligible_issue_count, 1)
        self.assertEqual(result.lifecycle_timing.testing_time_eligible_issue_count, 1)
        self.assertIsNone(result.lifecycle_timing.average_review_time_hours)

    def test_sprint_scope_and_repeated_output_are_deterministic(self) -> None:
        in_sprint = issue(1, IssueStatus.DONE, sprint_id=SPRINT_ID)
        other_sprint = issue(2, IssueStatus.TODO, sprint_id=OTHER_SPRINT_ID)

        first = report([in_sprint, other_sprint], selected_sprint=sprint())
        second = report([in_sprint, other_sprint], selected_sprint=sprint())

        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(first.scope.kind, "SPRINT")
        self.assertEqual(first.delivery.assigned_issue_count, 1)
        self.assertIn("currently associated", first.scope.definition)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
