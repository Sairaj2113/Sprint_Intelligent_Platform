from __future__ import annotations

import uuid

from pydantic import BaseModel


class IssueMetrics(BaseModel):
    total_issues: int
    completed_issues: int
    open_issues: int
    issue_completion_percentage: float


class StoryPointMetrics(BaseModel):
    total_story_points: int
    completed_story_points: int
    remaining_story_points: int
    story_point_completion_percentage: float


class BugMetrics(BaseModel):
    total_bugs: int
    resolved_bugs: int
    open_bugs: int


class StatusDistribution(BaseModel):
    todo: int
    in_progress: int
    code_review: int
    testing: int
    done: int


class EmployeeContributionMetrics(BaseModel):
    employee_id: uuid.UUID
    assigned_issues: int
    completed_issues: int
    assigned_story_points: int
    completed_story_points: int
    assigned_bugs: int
    resolved_bugs: int


class IssueDurationMetrics(BaseModel):
    cycle_time_hours: float | None
    development_time_hours: float | None
    review_time_hours: float | None
    testing_time_hours: float | None
    reopen_count: int


class AggregateDurationMetrics(BaseModel):
    average_cycle_time_hours: float | None
    average_development_time_hours: float | None
    average_review_time_hours: float | None
    average_testing_time_hours: float | None
