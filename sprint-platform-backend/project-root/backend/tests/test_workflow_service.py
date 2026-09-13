from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.issue import IssueStatus, IssueType
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.schemas.workflow import DeliveryStage, ProjectWorkflowEvidenceResponse, SprintWorkflowEvidenceResponse
from app.services.workflow_service import build_workflow_evidence


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SPRINT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
OTHER_SPRINT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD", name="RetailDialogue")


def sprint() -> SimpleNamespace:
    return SimpleNamespace(id=SPRINT_ID, name="Hardening", status=SprintStatus.ACTIVE)


def issue(
    issue_id: uuid.UUID,
    key: str,
    status: IssueStatus,
    *,
    sprint_id: uuid.UUID | None = SPRINT_ID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        issue_key=key,
        title=f"Title for {key}",
        issue_type=IssueType.TASK,
        status=status,
        story_points=5,
        sprint_id=sprint_id,
    )


def history(old: IssueStatus | None, new: IssueStatus, at: datetime) -> SimpleNamespace:
    return SimpleNamespace(old_status=old, new_status=new, changed_at=at)


class WorkflowServiceTests(unittest.TestCase):
    def test_empty_issue_scope_has_zero_summary_and_no_blocked_average(self) -> None:
        response = build_workflow_evidence(project(), [], {}, {}, {})

        self.assertIsInstance(response, ProjectWorkflowEvidenceResponse)
        self.assertEqual(response.summary.total_issues, 0)
        self.assertEqual(response.issues, [])
        self.assertIsNone(response.summary.average_blocked_time_hours)

    def test_delivery_stages_cover_current_workflow_states(self) -> None:
        issues = [
            issue(uuid.uuid4(), "RD-1", IssueStatus.TODO),
            issue(uuid.uuid4(), "RD-2", IssueStatus.IN_PROGRESS),
            issue(uuid.uuid4(), "RD-3", IssueStatus.CODE_REVIEW),
            issue(uuid.uuid4(), "RD-4", IssueStatus.TESTING),
            issue(uuid.uuid4(), "RD-5", IssueStatus.DONE),
            issue(uuid.uuid4(), "RD-6", IssueStatus.TODO),
        ]
        deployments = {issues[-1].id: [SimpleNamespace()]}
        response = build_workflow_evidence(project(), issues, {}, {}, deployments)

        self.assertEqual([item.delivery_stage for item in response.issues], [
            DeliveryStage.TODO,
            DeliveryStage.DEVELOPMENT,
            DeliveryStage.REVIEW,
            DeliveryStage.TESTING,
            DeliveryStage.DONE_NOT_DEPLOYED,
            DeliveryStage.DEPLOYED,
        ])
        self.assertEqual(response.summary.issues_deployed, 1)
        self.assertEqual(response.summary.issues_done_not_deployed, 1)

    def test_history_evidence_reuses_durations_and_ignores_noop_transitions(self) -> None:
        issue_id = uuid.uuid4()
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        histories = {
            issue_id: [
                history(IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=24)),
                history(IssueStatus.IN_PROGRESS, IssueStatus.IN_PROGRESS, start + timedelta(hours=2)),
                history(IssueStatus.DONE, IssueStatus.TESTING, start + timedelta(hours=30)),
                history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
                history(IssueStatus.IN_PROGRESS, IssueStatus.TESTING, start + timedelta(hours=12)),
            ]
        }
        response = build_workflow_evidence(
            project(), [issue(issue_id, "RD-7", IssueStatus.DONE)], histories,
            {issue_id: [SimpleNamespace(testing_status=TestingStatus.PASSED), SimpleNamespace(testing_status=TestingStatus.FAILED)]},
            {issue_id: [SimpleNamespace()]},
        )

        item = response.issues[0]
        self.assertEqual(item.transition_count, 4)
        self.assertEqual(item.reopen_count, 1)
        self.assertTrue(item.reached_testing)
        self.assertTrue(item.reached_done)
        self.assertEqual(item.cycle_time_hours, 24.0)
        self.assertEqual(item.development_time_hours, 12.0)
        self.assertIsNone(item.review_time_hours)
        self.assertEqual(item.testing_time_hours, 12.0)
        self.assertEqual(item.passed_test_count, 1)
        self.assertEqual(item.failed_test_count, 1)
        self.assertTrue(item.was_deployed)
        self.assertEqual(response.summary.total_reopen_count, 1)
        self.assertEqual(response.summary.issues_with_failed_test_evidence, 1)

    def test_incomplete_history_and_sprint_scope_are_safe(self) -> None:
        first = issue(uuid.uuid4(), "RD-8", IssueStatus.IN_PROGRESS, sprint_id=SPRINT_ID)
        second = issue(uuid.uuid4(), "RD-9", IssueStatus.DONE, sprint_id=OTHER_SPRINT_ID)
        response = build_workflow_evidence(
            project(), [first, second],
            {first.id: [history(None, IssueStatus.IN_PROGRESS, datetime(2026, 1, 1, tzinfo=timezone.utc))]},
            {}, {}, sprint=sprint(),
        )

        self.assertIsInstance(response, SprintWorkflowEvidenceResponse)
        self.assertEqual(response.summary.total_issues, 1)
        self.assertEqual(response.issues[0].issue_key, "RD-8")
        self.assertIsNone(response.issues[0].cycle_time_hours)
        self.assertFalse(response.issues[0].reached_testing)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
