from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.issue import IssueStatus, IssueType
from app.services.contribution_service import build_employee_contribution_evidence


EMPLOYEE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_EMPLOYEE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
PROJECT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SPRINT_ONE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SPRINT_TWO_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def employee() -> SimpleNamespace:
    return SimpleNamespace(id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj Pankar")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD", name="RetailDialogue")


def sprint(sprint_id: uuid.UUID, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=sprint_id, name=name)


def issue(
    issue_id: uuid.UUID,
    key: str,
    *,
    assignee_id: uuid.UUID | None,
    status: IssueStatus,
    issue_type: IssueType = IssueType.TASK,
    story_points: int | None = None,
    sprint_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        issue_key=key,
        title=f"Title for {key}",
        assignee_id=assignee_id,
        status=status,
        issue_type=issue_type,
        story_points=story_points,
        sprint_id=sprint_id,
    )


def history(
    old_status: IssueStatus | None,
    new_status: IssueStatus,
    changed_at: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(old_status=old_status, new_status=new_status, changed_at=changed_at)


def comment(issue_id: uuid.UUID, employee_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(issue_id=issue_id, employee_id=employee_id)


class ContributionServiceTests(unittest.TestCase):
    def test_employee_with_no_assigned_issues_keeps_comment_evidence_separate(self) -> None:
        other_issue_id = uuid.UUID("66666666-6666-6666-6666-666666666666")
        evidence = build_employee_contribution_evidence(
            employee(),
            project(),
            [issue(other_issue_id, "RD-1", assignee_id=OTHER_EMPLOYEE_ID, status=IssueStatus.TODO)],
            {}, {}, {},
            [comment(other_issue_id, EMPLOYEE_ID)],
        )

        self.assertEqual(evidence.summary.assigned_issues, 0)
        self.assertEqual(evidence.summary.issues_commented_on, 1)
        self.assertEqual(evidence.issues, [])

    def test_assigned_issue_evidence_uses_history_tests_and_deployments(self) -> None:
        issue_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        assigned_issue = issue(
            issue_id,
            "RD-2",
            assignee_id=EMPLOYEE_ID,
            status=IssueStatus.DONE,
            issue_type=IssueType.BUG,
            story_points=5,
            sprint_id=SPRINT_ONE_ID,
        )
        histories = {
            issue_id: [
                history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
                history(IssueStatus.IN_PROGRESS, IssueStatus.TESTING, start + timedelta(hours=12)),
                history(IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=24)),
                history(IssueStatus.DONE, IssueStatus.TESTING, start + timedelta(hours=30)),
            ]
        }
        evidence = build_employee_contribution_evidence(
            employee(), project(), [assigned_issue], histories,
            {issue_id: [SimpleNamespace(), SimpleNamespace()]},
            {issue_id: [SimpleNamespace()]},
            [comment(issue_id, EMPLOYEE_ID), comment(issue_id, EMPLOYEE_ID)],
            sprint_names_by_id={SPRINT_ONE_ID: "Sprint One"},
        )

        item = evidence.issues[0]
        self.assertTrue(item.reached_testing)
        self.assertTrue(item.was_deployed)
        self.assertEqual(item.test_result_count, 2)
        self.assertEqual(item.deployment_count, 1)
        self.assertEqual(item.reopen_count, 1)
        self.assertEqual(item.cycle_time_hours, 24.0)
        self.assertEqual(evidence.summary.issues_reaching_testing, 1)
        self.assertEqual(evidence.summary.issues_deployed, 1)
        self.assertEqual(evidence.summary.issues_commented_on, 1)
        self.assertEqual(evidence.summary.completed_story_points, 5)
        self.assertEqual(evidence.summary.resolved_bugs, 1)

    def test_incomplete_history_and_empty_evidence_collections_are_safe(self) -> None:
        issue_id = uuid.UUID("88888888-8888-8888-8888-888888888888")
        assigned_issue = issue(
            issue_id, "RD-3", assignee_id=EMPLOYEE_ID, status=IssueStatus.IN_PROGRESS
        )
        evidence = build_employee_contribution_evidence(
            employee(), project(), [assigned_issue],
            {issue_id: [history(None, IssueStatus.IN_PROGRESS, datetime(2026, 1, 1, tzinfo=timezone.utc))]},
            {}, {}, [],
        )

        item = evidence.issues[0]
        self.assertFalse(item.reached_testing)
        self.assertFalse(item.was_deployed)
        self.assertIsNone(item.cycle_time_hours)
        self.assertIsNone(evidence.summary.average_cycle_time_hours)

    def test_multiple_assigned_issues_are_the_only_delivery_contribution_scope(self) -> None:
        assigned_done = issue(
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            "RD-3A", assignee_id=EMPLOYEE_ID, status=IssueStatus.DONE, story_points=3,
        )
        assigned_open = issue(
            uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            "RD-3B", assignee_id=EMPLOYEE_ID, status=IssueStatus.TODO, story_points=5,
        )
        other_issue = issue(
            uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
            "RD-3C", assignee_id=OTHER_EMPLOYEE_ID, status=IssueStatus.DONE, story_points=8,
        )
        evidence = build_employee_contribution_evidence(
            employee(), project(), [assigned_done, assigned_open, other_issue], {}, {}, {}, []
        )

        self.assertEqual(evidence.summary.assigned_issues, 2)
        self.assertEqual(evidence.summary.completed_issues, 1)
        self.assertEqual(evidence.summary.assigned_story_points, 8)
        self.assertEqual(evidence.summary.completed_story_points, 3)
        self.assertEqual([item.issue_key for item in evidence.issues], ["RD-3A", "RD-3B"])

    def test_sprint_scope_only_counts_issues_in_requested_sprint(self) -> None:
        issue_one = issue(
            uuid.UUID("99999999-9999-9999-9999-999999999999"),
            "RD-4", assignee_id=EMPLOYEE_ID, status=IssueStatus.DONE, story_points=3,
            sprint_id=SPRINT_ONE_ID,
        )
        issue_two = issue(
            uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            "RD-5", assignee_id=EMPLOYEE_ID, status=IssueStatus.TODO, story_points=8,
            sprint_id=SPRINT_TWO_ID,
        )
        selected_sprint = sprint(SPRINT_ONE_ID, "Sprint One")
        evidence = build_employee_contribution_evidence(
            employee(), project(), [issue_one, issue_two], {}, {}, {}, [], sprint=selected_sprint
        )

        self.assertEqual(evidence.sprint_id, SPRINT_ONE_ID)
        self.assertEqual(evidence.summary.assigned_issues, 1)
        self.assertEqual(evidence.summary.completed_issues, 1)
        self.assertEqual(evidence.summary.assigned_story_points, 3)
        self.assertEqual(evidence.issues[0].sprint_name, "Sprint One")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
