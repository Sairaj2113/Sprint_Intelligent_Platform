"""Bulk, project-scoped retrieval of factual PostgreSQL evidence only."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Comment, Deployment, Employee, Issue, IssueHistory, Project, ProjectMember, Sprint, TestResult
from app.schemas.contribution import EmployeeContributionEvidence
from app.schemas.kpi import (
    AggregateDurationMetrics,
    BugMetrics,
    IssueMetrics,
    ProjectKpiResponse,
    SprintKpiResponse,
    StatusDistribution,
    StoryPointMetrics,
)
from app.schemas.workflow import ProjectWorkflowEvidenceResponse, SprintWorkflowEvidenceResponse
from app.services.contribution_service import build_employee_contribution_evidence
from app.services.kpi_service import (
    calculate_aggregate_duration_metrics,
    calculate_bug_metrics,
    calculate_issue_duration_metrics,
    calculate_issue_metrics,
    calculate_status_distribution,
    calculate_story_point_metrics,
)
from app.services.workflow_service import build_workflow_evidence


class StructuredEvidenceError(Exception):
    """Controlled error raised for invalid structured-evidence scope."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class StructuredProjectEvidence:
    id: UUID
    project_key: str
    name: str
    status: object
    methodology: object | None


@dataclass(frozen=True)
class StructuredEmployeeEvidence:
    id: UUID
    employee_code: str
    name: str
    role: str | None
    department: str | None


@dataclass(frozen=True)
class StructuredSprintEvidence:
    id: UUID
    name: str
    status: object
    start_date: object | None
    end_date: object | None


@dataclass(frozen=True)
class StructuredIssueEvidence:
    id: UUID
    issue_key: str
    title: str
    issue_type: object
    status: object
    story_points: int | None
    assignee_id: UUID | None
    assignee_name: str | None
    sprint_id: UUID | None
    sprint_name: str | None
    description: str | None
    acceptance_criteria: str | None
    technical_notes: str | None
    parent_issue_key: str | None
    parent_issue_title: str | None
    created_at: object
    completed_at: object | None


@dataclass(frozen=True)
class StructuredTestEvidence:
    id: UUID
    issue_id: UUID
    testing_status: object
    test_cases_total: int | None
    test_cases_passed: int | None
    bugs_found: int | None
    reopened_count: int | None
    tested_by: UUID | None
    tested_by_name: str | None
    tested_at: object | None
    testing_notes: str | None


@dataclass(frozen=True)
class StructuredDeploymentEvidence:
    id: UUID
    issue_id: UUID
    deployment_status: object
    environment: str | None
    deployment_date: object | None
    production_notes: str | None
    production_incidents: str | None


@dataclass(frozen=True)
class StructuredCommentEvidence:
    id: UUID
    issue_id: UUID
    employee_id: UUID
    employee_name: str | None
    content: str
    created_at: object


@dataclass(frozen=True)
class StructuredKpiEvidence:
    issue_metrics: IssueMetrics
    story_point_metrics: StoryPointMetrics
    bug_metrics: BugMetrics
    status_distribution: StatusDistribution
    duration_metrics: AggregateDurationMetrics


@dataclass(frozen=True)
class StructuredEvidencePackage:
    project: StructuredProjectEvidence
    employee: StructuredEmployeeEvidence | None
    sprint: StructuredSprintEvidence | None
    employee_scope_active: bool
    sprint_scope_active: bool
    issue_scope: str
    issues: list[StructuredIssueEvidence]
    tests: list[StructuredTestEvidence]
    deployments: list[StructuredDeploymentEvidence]
    comments: list[StructuredCommentEvidence]
    contribution: EmployeeContributionEvidence | None
    workflow: ProjectWorkflowEvidenceResponse | SprintWorkflowEvidenceResponse
    kpis: StructuredKpiEvidence
    warnings: list[str]

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    @property
    def test_evidence_count(self) -> int:
        return len(self.tests)

    @property
    def deployment_evidence_count(self) -> int:
        return len(self.deployments)

    @property
    def comment_evidence_count(self) -> int:
        return len(self.comments)


def _resolve_employee(reference: str, employees: Sequence[Employee]) -> Employee:
    normalized = reference.strip().casefold()
    exact_code = [employee for employee in employees if employee.employee_code.casefold() == normalized]
    exact_name = [employee for employee in employees if employee.name.casefold() == normalized]
    candidates = exact_code or exact_name
    if not candidates and " " not in normalized:
        candidates = [
            employee
            for employee in employees
            if employee.name.split(maxsplit=1)[0].casefold() == normalized
        ]
    if not candidates:
        raise StructuredEvidenceError("Project employee reference could not be resolved")
    if len(candidates) > 1:
        raise StructuredEvidenceError("Project employee reference is ambiguous")
    return candidates[0]


def _resolve_sprint(reference: str, sprints: Sequence[Sprint]) -> Sprint:
    normalized = reference.strip().casefold()
    exact_name = [sprint for sprint in sprints if sprint.name.casefold() == normalized]
    if len(exact_name) == 1:
        return exact_name[0]
    if len(exact_name) > 1:
        raise StructuredEvidenceError("Project sprint reference is ambiguous")

    import re

    match = re.fullmatch(r"sprint\s+([1-9]\d*)", normalized)
    if not match:
        raise StructuredEvidenceError("Project sprint reference could not be resolved")
    sprint_position = int(match.group(1)) - 1
    if sprint_position >= len(sprints):
        raise StructuredEvidenceError("Project sprint reference could not be resolved")
    return sprints[sprint_position]


def _load_related_evidence(
    db: Session, issue_ids: list[UUID]
) -> tuple[
    dict[UUID, list[IssueHistory]],
    list[TestResult],
    list[Deployment],
    list[Comment],
]:
    if not issue_ids:
        return {}, [], [], []
    histories_by_issue: dict[UUID, list[IssueHistory]] = defaultdict(list)
    for history in db.scalars(
        select(IssueHistory)
        .where(IssueHistory.issue_id.in_(issue_ids))
        .order_by(IssueHistory.changed_at)
    ):
        histories_by_issue[history.issue_id].append(history)
    tests = list(db.scalars(select(TestResult).where(TestResult.issue_id.in_(issue_ids))))
    deployments = list(db.scalars(select(Deployment).where(Deployment.issue_id.in_(issue_ids))))
    comments = list(db.scalars(select(Comment).where(Comment.issue_id.in_(issue_ids))))
    return histories_by_issue, tests, deployments, comments


def _group_by_issue(items: Sequence[object]) -> dict[UUID, list[object]]:
    grouped: dict[UUID, list[object]] = defaultdict(list)
    for item in items:
        grouped[item.issue_id].append(item)  # type: ignore[attr-defined]
    return grouped


def _build_kpis(
    project: Project, sprint: Sprint | None, issues: list[Issue], histories_by_issue: dict[UUID, list[IssueHistory]]
) -> StructuredKpiEvidence:
    duration_metrics = calculate_aggregate_duration_metrics(
        [calculate_issue_duration_metrics(histories_by_issue.get(issue.id, [])) for issue in issues]
    )
    return StructuredKpiEvidence(
        issue_metrics=calculate_issue_metrics(issues),
        story_point_metrics=calculate_story_point_metrics(issues),
        bug_metrics=calculate_bug_metrics(issues),
        status_distribution=calculate_status_distribution(issues),
        duration_metrics=duration_metrics,
    )


def build_structured_evidence(
    db: Session,
    project_key: str,
    employee_reference: str | None = None,
    sprint_reference: str | None = None,
) -> StructuredEvidencePackage:
    """Build a factual evidence package from bulk project-scoped database records."""
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise StructuredEvidenceError("Project not found", status_code=404)

    employees = list(
        db.scalars(
            select(Employee)
            .join(ProjectMember, ProjectMember.employee_id == Employee.id)
            .where(ProjectMember.project_id == project.id)
        )
    )
    sprints = list(
        db.scalars(
            select(Sprint)
            .where(Sprint.project_id == project.id)
            .order_by(Sprint.start_date, Sprint.created_at, Sprint.name)
        )
    )
    employee = _resolve_employee(employee_reference, employees) if employee_reference else None
    sprint = _resolve_sprint(sprint_reference, sprints) if sprint_reference else None

    issue_statement = select(Issue).where(Issue.project_id == project.id)
    if sprint is not None:
        issue_statement = issue_statement.where(Issue.sprint_id == sprint.id)
    if employee is not None:
        issue_statement = issue_statement.where(Issue.assignee_id == employee.id)
    issues = list(db.scalars(issue_statement))
    parent_issue_ids = {
        getattr(issue, "parent_issue_id", None)
        for issue in issues
        if getattr(issue, "parent_issue_id", None) is not None
    }
    parent_issues_by_id = {
        parent.id: parent
        for parent in db.scalars(
            select(Issue).where(
                Issue.project_id == project.id,
                Issue.id.in_(parent_issue_ids),
            )
        )
    } if parent_issue_ids else {}
    histories_by_issue, tests, deployments, comments = _load_related_evidence(
        db, [issue.id for issue in issues]
    )

    employees_by_id = {item.id: item for item in employees}
    sprint_names_by_id = {item.id: item.name for item in sprints}
    tests_by_issue = _group_by_issue(tests)
    deployments_by_issue = _group_by_issue(deployments)

    contribution = (
        build_employee_contribution_evidence(
            employee,
            project,
            issues,
            histories_by_issue,
            tests_by_issue,
            deployments_by_issue,
            comments,
            sprint=sprint,
            sprint_names_by_id=sprint_names_by_id,
        )
        if employee is not None
        else None
    )
    workflow = build_workflow_evidence(
        project,
        issues,
        histories_by_issue,
        tests_by_issue,
        deployments_by_issue,
        sprint=sprint,
        sprint_names_by_id=sprint_names_by_id,
    )
    warnings: list[str] = []
    if employee is not None and not issues:
        warnings.append("Employee has no assigned issues in the selected scope")
    if sprint is not None and not issues:
        warnings.append("Sprint contains no issues in the selected scope")
    if not tests:
        warnings.append("Selected issue scope has no tests")
    if not deployments:
        warnings.append("Selected issue scope has no deployments")

    issue_scope = (
        "EMPLOYEE_ASSIGNED_SPRINT" if employee is not None and sprint is not None
        else "EMPLOYEE_ASSIGNED" if employee is not None
        else "SPRINT" if sprint is not None
        else "PROJECT"
    )
    return StructuredEvidencePackage(
        project=StructuredProjectEvidence(
            id=project.id,
            project_key=project.project_key,
            name=project.name,
            status=project.status,
            methodology=project.methodology,
        ),
        employee=(
            StructuredEmployeeEvidence(
                id=employee.id,
                employee_code=employee.employee_code,
                name=employee.name,
                role=employee.role,
                department=employee.department,
            )
            if employee is not None
            else None
        ),
        sprint=(
            StructuredSprintEvidence(
                id=sprint.id,
                name=sprint.name,
                status=sprint.status,
                start_date=sprint.start_date,
                end_date=sprint.end_date,
            )
            if sprint is not None
            else None
        ),
        employee_scope_active=employee is not None,
        sprint_scope_active=sprint is not None,
        issue_scope=issue_scope,
        issues=[
            StructuredIssueEvidence(
                id=issue.id,
                issue_key=issue.issue_key,
                title=issue.title,
                issue_type=issue.issue_type,
                status=issue.status,
                story_points=issue.story_points,
                assignee_id=issue.assignee_id,
                assignee_name=(
                    employees_by_id[issue.assignee_id].name
                    if issue.assignee_id in employees_by_id
                    else None
                ),
                sprint_id=issue.sprint_id,
                sprint_name=sprint_names_by_id.get(issue.sprint_id),
                description=getattr(issue, "description", None),
                acceptance_criteria=getattr(issue, "acceptance_criteria", None),
                technical_notes=getattr(issue, "technical_notes", None),
                parent_issue_key=(
                    parent_issues_by_id[getattr(issue, "parent_issue_id", None)].issue_key
                    if getattr(issue, "parent_issue_id", None) in parent_issues_by_id
                    else None
                ),
                parent_issue_title=(
                    parent_issues_by_id[getattr(issue, "parent_issue_id", None)].title
                    if getattr(issue, "parent_issue_id", None) in parent_issues_by_id
                    else None
                ),
                created_at=issue.created_at,
                completed_at=issue.completed_at,
            )
            for issue in issues
        ],
        tests=[
            StructuredTestEvidence(
                id=item.id,
                issue_id=item.issue_id,
                testing_status=item.testing_status,
                test_cases_total=item.test_cases_total,
                test_cases_passed=item.test_cases_passed,
                bugs_found=item.bugs_found,
                reopened_count=item.reopened_count,
                tested_by=item.tested_by,
                tested_by_name=(
                    employees_by_id[item.tested_by].name
                    if item.tested_by in employees_by_id
                    else None
                ),
                tested_at=item.tested_at,
                testing_notes=getattr(item, "testing_notes", None),
            )
            for item in tests
        ],
        deployments=[
            StructuredDeploymentEvidence(
                id=item.id,
                issue_id=item.issue_id,
                deployment_status=item.deployment_status,
                environment=item.environment,
                deployment_date=item.deployment_date,
                production_notes=item.production_notes,
                production_incidents=item.production_incidents,
            )
            for item in deployments
        ],
        comments=[
            StructuredCommentEvidence(
                id=item.id,
                issue_id=item.issue_id,
                employee_id=item.employee_id,
                employee_name=(
                    employees_by_id[item.employee_id].name
                    if item.employee_id in employees_by_id
                    else None
                ),
                content=item.content,
                created_at=item.created_at,
            )
            for item in comments
        ],
        contribution=contribution,
        workflow=workflow,
        kpis=_build_kpis(project, sprint, issues, histories_by_issue),
        warnings=warnings,
    )
