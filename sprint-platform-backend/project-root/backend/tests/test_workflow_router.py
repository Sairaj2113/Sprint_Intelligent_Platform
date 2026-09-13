from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

from app.models.issue import IssueStatus, IssueType
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.routers.workflow import get_project_workflow_evidence, get_sprint_workflow_evidence


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SPRINT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ISSUE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD", name="RetailDialogue")


def sprint() -> SimpleNamespace:
    return SimpleNamespace(
        id=SPRINT_ID,
        project_id=PROJECT_ID,
        name="Reliability and Release Hardening",
        status=SprintStatus.ACTIVE,
    )


def issue(issue_id: uuid.UUID, key: str, status: IssueStatus = IssueStatus.DONE) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        issue_key=key,
        title=f"Title for {key}",
        issue_type=IssueType.TASK,
        status=status,
        story_points=5,
        sprint_id=SPRINT_ID,
    )


def history(issue_id: uuid.UUID, old: IssueStatus | None, new: IssueStatus, at: datetime) -> SimpleNamespace:
    return SimpleNamespace(issue_id=issue_id, old_status=old, new_status=new, changed_at=at)


class WorkflowRouterTests(unittest.TestCase):
    def test_valid_project_workflow_uses_bulk_evidence_and_sprint_names(self) -> None:
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        db = Mock()
        db.scalar.return_value = project()
        db.scalars.side_effect = [
            [issue(ISSUE_ID, "RD-1")],
            [
                history(ISSUE_ID, IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
                history(ISSUE_ID, IssueStatus.IN_PROGRESS, IssueStatus.DONE, start + timedelta(hours=24)),
            ],
            [SimpleNamespace(issue_id=ISSUE_ID, testing_status=TestingStatus.PASSED)],
            [SimpleNamespace(issue_id=ISSUE_ID)],
            [sprint()],
        ]

        response = get_project_workflow_evidence("RD", db)

        self.assertEqual(response.summary.total_issues, 1)
        self.assertEqual(response.issues[0].sprint_name, "Reliability and Release Hardening")
        self.assertEqual(response.issues[0].cycle_time_hours, 24.0)
        self.assertEqual(response.issues[0].passed_test_count, 1)
        self.assertEqual(db.scalars.call_count, 5)

    def test_invalid_project_returns_404(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as error:
            get_project_workflow_evidence("MISSING", db)

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Project not found")

    def test_valid_sprint_workflow_and_cross_project_sprint_404(self) -> None:
        db = Mock()
        db.scalar.side_effect = [project(), sprint()]
        db.scalars.side_effect = [[issue(ISSUE_ID, "RD-2", IssueStatus.TESTING)], [], [], []]

        response = get_sprint_workflow_evidence("RD", SPRINT_ID, db)

        self.assertEqual(response.sprint_id, SPRINT_ID)
        self.assertEqual(response.summary.issues_in_testing, 1)
        self.assertEqual(db.scalars.call_count, 4)

        other_sprint_db = Mock()
        other_sprint_db.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as error:
            get_sprint_workflow_evidence("RD", SPRINT_ID, other_sprint_db)
        self.assertEqual(error.exception.detail, "Sprint not found")

    def test_zero_issue_project_returns_valid_empty_response(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        db.scalars.side_effect = [[], []]

        response = get_project_workflow_evidence("RD", db)

        self.assertEqual(response.summary.total_issues, 0)
        self.assertEqual(response.issues, [])
        self.assertIsNone(response.summary.average_blocked_time_hours)
        self.assertEqual(db.scalars.call_count, 2)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
