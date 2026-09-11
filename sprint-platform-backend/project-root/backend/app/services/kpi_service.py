"""Deterministic KPI calculations derived from existing issue records."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from app.models.issue import Issue, IssueStatus, IssueType
from app.models.issue_history import IssueHistory
from app.schemas.kpi import (
    AggregateDurationMetrics,
    BugMetrics,
    EmployeeContributionMetrics,
    IssueDurationMetrics,
    IssueMetrics,
    StatusDistribution,
    StoryPointMetrics,
)


def calculate_issue_metrics(issues: Iterable[Issue]) -> IssueMetrics:
    """Return issue completion counts using DONE as the only completed status."""
    issue_list = list(issues)
    completed_issues = sum(issue.status == IssueStatus.DONE for issue in issue_list)
    total_issues = len(issue_list)
    return IssueMetrics(
        total_issues=total_issues,
        completed_issues=completed_issues,
        open_issues=total_issues - completed_issues,
        issue_completion_percentage=(completed_issues / total_issues * 100) if total_issues else 0.0,
    )


def calculate_story_point_metrics(issues: Iterable[Issue]) -> StoryPointMetrics:
    """Return story-point totals while ignoring issues without story points."""
    total_story_points = 0
    completed_story_points = 0
    for issue in issues:
        if issue.story_points is None:
            continue
        total_story_points += issue.story_points
        if issue.status == IssueStatus.DONE:
            completed_story_points += issue.story_points

    return StoryPointMetrics(
        total_story_points=total_story_points,
        completed_story_points=completed_story_points,
        remaining_story_points=total_story_points - completed_story_points,
        story_point_completion_percentage=(completed_story_points / total_story_points * 100)
        if total_story_points
        else 0.0,
    )


def calculate_bug_metrics(issues: Iterable[Issue]) -> BugMetrics:
    """Return factual counts for issues whose type is BUG."""
    bugs = [issue for issue in issues if issue.issue_type == IssueType.BUG]
    resolved_bugs = sum(issue.status == IssueStatus.DONE for issue in bugs)
    return BugMetrics(
        total_bugs=len(bugs),
        resolved_bugs=resolved_bugs,
        open_bugs=len(bugs) - resolved_bugs,
    )


def calculate_status_distribution(issues: Iterable[Issue]) -> StatusDistribution:
    """Return counts for the workflow statuses surfaced by delivery views."""
    counts = {
        IssueStatus.TODO: 0,
        IssueStatus.IN_PROGRESS: 0,
        IssueStatus.CODE_REVIEW: 0,
        IssueStatus.TESTING: 0,
        IssueStatus.DONE: 0,
    }
    for issue in issues:
        if issue.status in counts:
            counts[issue.status] += 1

    return StatusDistribution(
        todo=counts[IssueStatus.TODO],
        in_progress=counts[IssueStatus.IN_PROGRESS],
        code_review=counts[IssueStatus.CODE_REVIEW],
        testing=counts[IssueStatus.TESTING],
        done=counts[IssueStatus.DONE],
    )


def calculate_employee_contribution_metrics(
    employee_id: UUID,
    issues: Iterable[Issue],
) -> EmployeeContributionMetrics:
    """Return assignment counts only; these metrics are not performance ratings."""
    assigned_issues = [issue for issue in issues if issue.assignee_id == employee_id]
    completed_issues = sum(issue.status == IssueStatus.DONE for issue in assigned_issues)
    assigned_story_points = sum(issue.story_points or 0 for issue in assigned_issues)
    completed_story_points = sum(
        issue.story_points or 0 for issue in assigned_issues if issue.status == IssueStatus.DONE
    )
    assigned_bugs = [issue for issue in assigned_issues if issue.issue_type == IssueType.BUG]
    resolved_bugs = sum(issue.status == IssueStatus.DONE for issue in assigned_bugs)

    return EmployeeContributionMetrics(
        employee_id=employee_id,
        assigned_issues=len(assigned_issues),
        completed_issues=completed_issues,
        assigned_story_points=assigned_story_points,
        completed_story_points=completed_story_points,
        assigned_bugs=len(assigned_bugs),
        resolved_bugs=resolved_bugs,
    )


HistoryEntry = TypeVar("HistoryEntry", bound=IssueHistory)


def _chronological(history: Iterable[HistoryEntry]) -> list[HistoryEntry]:
    return sorted(history, key=lambda entry: entry.changed_at)


def _first_transition_index(
    history: Sequence[IssueHistory],
    statuses: set[IssueStatus],
    start_index: int = 0,
) -> int | None:
    for index in range(start_index, len(history)):
        if history[index].new_status in statuses:
            return index
    return None


def _duration_hours(started_at: datetime, ended_at: datetime) -> float:
    return (ended_at - started_at).total_seconds() / 3600


def _duration_between_transitions(
    history: Sequence[IssueHistory],
    start_status: IssueStatus,
    end_statuses: set[IssueStatus],
) -> float | None:
    start_index = _first_transition_index(history, {start_status})
    if start_index is None:
        return None

    end_index = _first_transition_index(history, end_statuses, start_index + 1)
    if end_index is None:
        return None

    return _duration_hours(history[start_index].changed_at, history[end_index].changed_at)


def calculate_issue_duration_metrics(history: Iterable[IssueHistory]) -> IssueDurationMetrics:
    """Reconstruct duration metrics from chronologically ordered status transitions."""
    ordered_history = _chronological(history)
    cycle_time_hours = _duration_between_transitions(
        ordered_history,
        IssueStatus.IN_PROGRESS,
        {IssueStatus.DONE},
    )
    development_time_hours = _duration_between_transitions(
        ordered_history,
        IssueStatus.IN_PROGRESS,
        {IssueStatus.CODE_REVIEW, IssueStatus.TESTING, IssueStatus.DONE},
    )
    review_time_hours = _duration_between_transitions(
        ordered_history,
        IssueStatus.CODE_REVIEW,
        {IssueStatus.TESTING, IssueStatus.DONE},
    )
    testing_time_hours = _duration_between_transitions(
        ordered_history,
        IssueStatus.TESTING,
        {IssueStatus.DONE},
    )
    reopen_count = sum(
        entry.old_status == IssueStatus.DONE and entry.new_status != IssueStatus.DONE
        for entry in ordered_history
    )
    return IssueDurationMetrics(
        cycle_time_hours=cycle_time_hours,
        development_time_hours=development_time_hours,
        review_time_hours=review_time_hours,
        testing_time_hours=testing_time_hours,
        reopen_count=reopen_count,
    )


def _average(values: Iterable[float | None]) -> float | None:
    available_values = [value for value in values if value is not None]
    return sum(available_values) / len(available_values) if available_values else None


def calculate_aggregate_duration_metrics(
    duration_metrics: Iterable[IssueDurationMetrics],
) -> AggregateDurationMetrics:
    """Average available duration values and leave unavailable averages as None."""
    metrics = list(duration_metrics)
    return AggregateDurationMetrics(
        average_cycle_time_hours=_average(metric.cycle_time_hours for metric in metrics),
        average_development_time_hours=_average(
            metric.development_time_hours for metric in metrics
        ),
        average_review_time_hours=_average(metric.review_time_hours for metric in metrics),
        average_testing_time_hours=_average(metric.testing_time_hours for metric in metrics),
    )
