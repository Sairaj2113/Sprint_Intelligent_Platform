from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

from app.models.issue import IssueStatus, IssueType
from app.models.sprint import SprintStatus
from app.routers.contributions import (
    get_project_employee_contribution,
    get_sprint_employee_contribution,
)


EMPLOYEE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SPRINT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
ISSUE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
OTHER_ISSUE_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")


def employee() -> SimpleNamespace:
    return SimpleNamespace(id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj Pankar")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD", name="RetailDialogue")


def sprint() -> SimpleNamespace:
    return SimpleNamespace(
        id=SPRINT_ID,
        project_id=PROJECT_ID,
        name="Reliability and Release Hardening",
        status=SprintStatus.ACTIVE,
    )


def issue(
    issue_id: uuid.UUID,
    key: str,
    *,
    assignee_id: uuid.UUID | None,
    status: IssueStatus = IssueStatus.TODO,
    sprint_id: uuid.UUID | None = SPRINT_ID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        issue_key=key,
        title=f"Title for {key}",
        assignee_id=assignee_id,
        status=status,
        issue_type=IssueType.TASK,
        story_points=5,
        sprint_id=sprint_id,
    )


def history(issue_id: uuid.UUID, old: IssueStatus | None, new: IssueStatus, at: datetime) -> SimpleNamespace:
    return SimpleNamespace(issue_id=issue_id, old_status=old, new_status=new, changed_at=at)


def comment(issue_id: uuid.UUID, employee_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(issue_id=issue_id, employee_id=employee_id)


class ContributionRouterTests(unittest.TestCase):
    def _project_db(self, issues: list[SimpleNamespace], comments: list[SimpleNamespace]) -> Mock:
        db = Mock()
        db.scalar.side_effect = [project(), employee(), uuid.uuid4()]
        db.scalars.side_effect = [issues, [], [], [], comments, [sprint()]]
        return db

    def test_valid_project_contribution_loads_bulk_evidence_and_sprint_names(self) -> None:
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        assigned = issue(ISSUE_ID, "RD-1", assignee_id=EMPLOYEE_ID, status=IssueStatus.DONE)
        other = issue(OTHER_ISSUE_ID, "RD-2", assignee_id=uuid.uuid4())
        db = Mock()
        db.scalar.side_effect = [project(), employee(), uuid.uuid4()]
        db.scalars.side_effect = [
            [assigned, other],
            [
                history(ISSUE_ID, IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
                history(ISSUE_ID, IssueStatus.IN_PROGRESS, IssueStatus.TESTING, start + timedelta(hours=8)),
                history(ISSUE_ID, IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=16)),
            ],
            [SimpleNamespace(issue_id=ISSUE_ID)],
            [SimpleNamespace(issue_id=ISSUE_ID)],
            [comment(OTHER_ISSUE_ID, EMPLOYEE_ID)],
            [sprint()],
        ]

        response = get_project_employee_contribution("RD", EMPLOYEE_ID, db)

        self.assertEqual(response.summary.assigned_issues, 1)
        self.assertEqual(response.summary.issues_commented_on, 1)
        self.assertEqual(response.issues[0].sprint_name, "Reliability and Release Hardening")
        self.assertTrue(response.issues[0].reached_testing)
        self.assertEqual(response.issues[0].test_result_count, 1)
        self.assertEqual(response.issues[0].deployment_count, 1)
        self.assertEqual(db.scalars.call_count, 6)

    def test_missing_project_employee_and_membership_return_404(self) -> None:
        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as project_error:
            get_project_employee_contribution("MISSING", EMPLOYEE_ID, missing_project_db)
        self.assertEqual(project_error.exception.detail, "Project not found")

        missing_employee_db = Mock()
        missing_employee_db.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as employee_error:
            get_project_employee_contribution("RD", EMPLOYEE_ID, missing_employee_db)
        self.assertEqual(employee_error.exception.detail, "Employee not found")

        missing_member_db = Mock()
        missing_member_db.scalar.side_effect = [project(), employee(), None]
        with self.assertRaises(HTTPException) as member_error:
            get_project_employee_contribution("RD", EMPLOYEE_ID, missing_member_db)
        self.assertEqual(member_error.exception.detail, "Project member not found")

    def test_valid_sprint_contribution_and_cross_project_sprint_404(self) -> None:
        scoped_issue = issue(ISSUE_ID, "RD-3", assignee_id=EMPLOYEE_ID)
        db = Mock()
        db.scalar.side_effect = [project(), employee(), uuid.uuid4(), sprint()]
        db.scalars.side_effect = [[scoped_issue], [], [], [], []]

        response = get_sprint_employee_contribution("RD", SPRINT_ID, EMPLOYEE_ID, db)

        self.assertEqual(response.sprint_id, SPRINT_ID)
        self.assertEqual(response.sprint_name, "Reliability and Release Hardening")
        self.assertEqual(response.summary.assigned_issues, 1)
        self.assertEqual(db.scalars.call_count, 5)

        other_sprint_db = Mock()
        other_sprint_db.scalar.side_effect = [project(), employee(), uuid.uuid4(), None]
        with self.assertRaises(HTTPException) as sprint_error:
            get_sprint_employee_contribution("RD", SPRINT_ID, EMPLOYEE_ID, other_sprint_db)
        self.assertEqual(sprint_error.exception.detail, "Sprint not found")

    def test_valid_member_with_zero_assigned_issues_returns_empty_evidence(self) -> None:
        other_issue = issue(OTHER_ISSUE_ID, "RD-4", assignee_id=uuid.uuid4())
        db = self._project_db([other_issue], [])

        response = get_project_employee_contribution("RD", EMPLOYEE_ID, db)

        self.assertEqual(response.summary.assigned_issues, 0)
        self.assertEqual(response.issues, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
