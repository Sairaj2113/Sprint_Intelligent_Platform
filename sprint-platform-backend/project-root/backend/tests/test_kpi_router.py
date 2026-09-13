from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

from app.models.issue import IssueStatus, IssueType
from app.models.sprint import SprintStatus
from app.routers.kpis import get_project_kpis, get_sprint_kpis


def issue(
    issue_id: uuid.UUID,
    *,
    status: IssueStatus,
    issue_type: IssueType = IssueType.TASK,
    story_points: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        status=status,
        issue_type=issue_type,
        story_points=story_points,
    )


def history(
    issue_id: uuid.UUID,
    old_status: IssueStatus | None,
    new_status: IssueStatus,
    changed_at: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        issue_id=issue_id,
        old_status=old_status,
        new_status=new_status,
        changed_at=changed_at,
    )


class KpiRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        self.sprint_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        self.project = SimpleNamespace(id=self.project_id, project_key="RD")
        self.sprint = SimpleNamespace(
            id=self.sprint_id,
            project_id=self.project_id,
            name="Reliability and Release Hardening",
            status=SprintStatus.ACTIVE,
        )

    def test_valid_project_kpis_include_duration_aggregation(self) -> None:
        issue_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        issues = [issue(issue_id, status=IssueStatus.DONE, issue_type=IssueType.BUG, story_points=5)]
        histories = [
            history(issue_id, IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
            history(issue_id, IssueStatus.IN_PROGRESS, IssueStatus.DONE, start + timedelta(hours=24)),
        ]
        db = Mock()
        db.scalar.return_value = self.project
        db.scalars.side_effect = [issues, histories]

        response = get_project_kpis("RD", db)

        self.assertEqual(response.project_key, "RD")
        self.assertEqual(response.issue_metrics.completed_issues, 1)
        self.assertEqual(response.story_point_metrics.completed_story_points, 5)
        self.assertEqual(response.bug_metrics.resolved_bugs, 1)
        self.assertEqual(response.duration_metrics.average_cycle_time_hours, 24.0)
        self.assertEqual(response.status_distribution.done, 1)

    def test_invalid_project_returns_404(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        with self.assertRaises(HTTPException) as error:
            get_project_kpis("MISSING", db)

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Project not found")

    def test_valid_sprint_kpis_only_use_sprint_issues(self) -> None:
        issue_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
        db = Mock()
        db.scalar.side_effect = [self.project, self.sprint]
        db.scalars.side_effect = [[issue(issue_id, status=IssueStatus.TODO, story_points=3)], []]

        response = get_sprint_kpis("RD", self.sprint_id, db)

        self.assertEqual(response.sprint_id, self.sprint_id)
        self.assertEqual(response.sprint_name, self.sprint.name)
        self.assertEqual(response.issue_metrics.total_issues, 1)
        self.assertEqual(response.issue_metrics.open_issues, 1)
        self.assertEqual(response.duration_metrics.average_cycle_time_hours, None)

    def test_sprint_from_another_project_returns_404(self) -> None:
        db = Mock()
        db.scalar.side_effect = [self.project, None]

        with self.assertRaises(HTTPException) as error:
            get_sprint_kpis("RD", self.sprint_id, db)

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Sprint not found")

    def test_project_with_zero_issues_has_empty_kpi_groups(self) -> None:
        db = Mock()
        db.scalar.return_value = self.project
        db.scalars.return_value = []

        response = get_project_kpis("RD", db)

        self.assertEqual(response.issue_metrics.total_issues, 0)
        self.assertEqual(response.story_point_metrics.total_story_points, 0)
        self.assertEqual(response.bug_metrics.total_bugs, 0)
        self.assertEqual(response.duration_metrics.model_dump(), {
            "average_cycle_time_hours": None,
            "average_development_time_hours": None,
            "average_review_time_hours": None,
            "average_testing_time_hours": None,
        })


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
