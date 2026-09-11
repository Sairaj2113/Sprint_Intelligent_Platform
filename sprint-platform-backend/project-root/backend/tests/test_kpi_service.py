from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models.issue import IssueStatus, IssueType
from app.schemas.kpi import IssueDurationMetrics
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_bug_metrics,
    calculate_employee_contribution_metrics,
    calculate_issue_duration_metrics,
    calculate_issue_metrics,
    calculate_status_distribution,
    calculate_story_point_metrics,
)


def issue(
    *,
    status: IssueStatus,
    issue_type: IssueType = IssueType.TASK,
    story_points: int | None = None,
    assignee_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        issue_type=issue_type,
        story_points=story_points,
        assignee_id=assignee_id,
    )


def history(
    old_status: IssueStatus | None,
    new_status: IssueStatus,
    changed_at: datetime,
) -> SimpleNamespace:
    return SimpleNamespace(
        old_status=old_status,
        new_status=new_status,
        changed_at=changed_at,
    )


class KpiServiceTests(unittest.TestCase):
    def test_empty_issue_metrics(self) -> None:
        self.assertEqual(calculate_issue_metrics([]).model_dump(), {
            "total_issues": 0,
            "completed_issues": 0,
            "open_issues": 0,
            "issue_completion_percentage": 0.0,
        })
        self.assertEqual(calculate_story_point_metrics([]).total_story_points, 0)
        self.assertEqual(calculate_bug_metrics([]).total_bugs, 0)
        self.assertEqual(calculate_status_distribution([]).model_dump(), {
            "todo": 0,
            "in_progress": 0,
            "code_review": 0,
            "testing": 0,
            "done": 0,
        })

    def test_all_done_issues_and_null_story_points(self) -> None:
        issues = [
            issue(status=IssueStatus.DONE, story_points=5),
            issue(status=IssueStatus.DONE, story_points=None),
        ]
        self.assertEqual(calculate_issue_metrics(issues).issue_completion_percentage, 100.0)
        self.assertEqual(calculate_story_point_metrics(issues).model_dump(), {
            "total_story_points": 5,
            "completed_story_points": 5,
            "remaining_story_points": 0,
            "story_point_completion_percentage": 100.0,
        })

    def test_mixed_statuses_bugs_and_employee_assignments(self) -> None:
        employee_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        other_employee_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        issues = [
            issue(status=IssueStatus.DONE, issue_type=IssueType.BUG, story_points=3, assignee_id=employee_id),
            issue(status=IssueStatus.TESTING, issue_type=IssueType.BUG, story_points=5, assignee_id=employee_id),
            issue(status=IssueStatus.IN_PROGRESS, story_points=None, assignee_id=employee_id),
            issue(status=IssueStatus.TODO, story_points=8, assignee_id=other_employee_id),
        ]
        self.assertEqual(calculate_issue_metrics(issues).model_dump(), {
            "total_issues": 4,
            "completed_issues": 1,
            "open_issues": 3,
            "issue_completion_percentage": 25.0,
        })
        self.assertEqual(calculate_bug_metrics(issues).model_dump(), {
            "total_bugs": 2,
            "resolved_bugs": 1,
            "open_bugs": 1,
        })
        self.assertEqual(calculate_status_distribution(issues).model_dump(), {
            "todo": 1,
            "in_progress": 1,
            "code_review": 0,
            "testing": 1,
            "done": 1,
        })
        self.assertEqual(calculate_employee_contribution_metrics(employee_id, issues).model_dump(), {
            "employee_id": employee_id,
            "assigned_issues": 3,
            "completed_issues": 1,
            "assigned_story_points": 8,
            "completed_story_points": 3,
            "assigned_bugs": 2,
            "resolved_bugs": 1,
        })

    def test_normal_history_is_sorted_before_duration_calculation(self) -> None:
        start = datetime(2026, 1, 1, 9, tzinfo=timezone.utc)
        transitions = [
            history(IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=72)),
            history(IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, start + timedelta(hours=24)),
            history(IssueStatus.CODE_REVIEW, IssueStatus.TESTING, start + timedelta(hours=48)),
            history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
        ]
        metrics = calculate_issue_duration_metrics(transitions)
        self.assertEqual(metrics.cycle_time_hours, 72.0)
        self.assertEqual(metrics.development_time_hours, 24.0)
        self.assertEqual(metrics.review_time_hours, 24.0)
        self.assertEqual(metrics.testing_time_hours, 24.0)

    def test_duration_fallbacks_for_skipped_review_and_testing(self) -> None:
        start = datetime(2026, 1, 2, 9, tzinfo=timezone.utc)
        skipped_review = [
            history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
            history(IssueStatus.IN_PROGRESS, IssueStatus.TESTING, start + timedelta(hours=12)),
            history(IssueStatus.TESTING, IssueStatus.DONE, start + timedelta(hours=24)),
        ]
        review_metrics = calculate_issue_duration_metrics(skipped_review)
        self.assertEqual(review_metrics.development_time_hours, 12.0)
        self.assertIsNone(review_metrics.review_time_hours)
        self.assertEqual(review_metrics.testing_time_hours, 12.0)

        skipped_testing = [
            history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start),
            history(IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, start + timedelta(hours=12)),
            history(IssueStatus.CODE_REVIEW, IssueStatus.DONE, start + timedelta(hours=24)),
        ]
        testing_metrics = calculate_issue_duration_metrics(skipped_testing)
        self.assertEqual(testing_metrics.development_time_hours, 12.0)
        self.assertEqual(testing_metrics.review_time_hours, 12.0)
        self.assertIsNone(testing_metrics.testing_time_hours)

    def test_incomplete_history_and_reopened_issue(self) -> None:
        start = datetime(2026, 1, 3, 9, tzinfo=timezone.utc)
        incomplete = [history(IssueStatus.TODO, IssueStatus.IN_PROGRESS, start)]
        metrics = calculate_issue_duration_metrics(incomplete)
        self.assertIsNone(metrics.cycle_time_hours)
        self.assertIsNone(metrics.development_time_hours)

        reopened = incomplete + [
            history(IssueStatus.IN_PROGRESS, IssueStatus.DONE, start + timedelta(hours=12)),
            history(IssueStatus.DONE, IssueStatus.TESTING, start + timedelta(hours=24)),
        ]
        self.assertEqual(calculate_issue_duration_metrics(reopened).reopen_count, 1)

    def test_duration_averages_ignore_missing_values(self) -> None:
        aggregate = calculate_aggregate_duration_metrics([
            IssueDurationMetrics(
                cycle_time_hours=24.0,
                development_time_hours=8.0,
                review_time_hours=None,
                testing_time_hours=4.0,
                reopen_count=0,
            ),
            IssueDurationMetrics(
                cycle_time_hours=None,
                development_time_hours=16.0,
                review_time_hours=None,
                testing_time_hours=8.0,
                reopen_count=1,
            ),
        ])
        self.assertEqual(aggregate.average_cycle_time_hours, 24.0)
        self.assertEqual(aggregate.average_development_time_hours, 12.0)
        self.assertIsNone(aggregate.average_review_time_hours)
        self.assertEqual(aggregate.average_testing_time_hours, 6.0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
