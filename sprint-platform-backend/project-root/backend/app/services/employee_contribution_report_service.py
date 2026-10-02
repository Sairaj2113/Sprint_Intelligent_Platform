"""Pure construction of current-assignment employee contribution reports."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from uuid import UUID

from app.models.comment import Comment
from app.models.deployment import Deployment
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.employee import Employee
from app.models.issue import Issue, IssueStatus
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.requirement_trace_link import RequirementTraceLink, RequirementTraceLinkKind
from app.models.sprint import Sprint
from app.models.test_result import TestResult
from app.schemas.employee_contribution_report import (
    AuthoredCommentContribution,
    CanonicalRequirementDocumentContext,
    ContributionAttributionBasis,
    ContributionEmployee,
    ContributionEvidenceCoverage,
    ContributionLinkBasis,
    ContributionProject,
    ContributionScope,
    CurrentSprintContext,
    CurrentlyAssignedIssueContribution,
    EmployeeContributionReport,
    ExplicitRequirementConnection,
    LinkedDeploymentContribution,
    LinkedTestContribution,
    TraceVerificationMetadata,
)


def build_employee_contribution_report(
    employee: Employee,
    project: Project,
    issues: Iterable[Issue],
    comments: Iterable[Comment],
    tests: Iterable[TestResult],
    deployments: Iterable[Deployment],
    requirement_trace_links: Iterable[RequirementTraceLink],
    requirements_by_id: Mapping[UUID, Requirement],
    canonical_sources_by_requirement_id: Mapping[UUID, tuple[DocumentChunk, Document]],
    sprints_by_id: Mapping[UUID, Sprint],
    *,
    sprint: Sprint | None = None,
) -> EmployeeContributionReport:
    """Build deterministic evidence without I/O or historical attribution inference."""
    scoped_issues = sorted(issues, key=lambda issue: (issue.issue_key, str(issue.id)))
    if sprint is not None:
        scoped_issues = [issue for issue in scoped_issues if issue.sprint_id == sprint.id]
    assigned_issues = [issue for issue in scoped_issues if issue.assignee_id == employee.id]
    assigned_issue_ids = {issue.id for issue in assigned_issues}
    issue_keys = {issue.id: issue.issue_key for issue in scoped_issues}

    assigned_records = [
        CurrentlyAssignedIssueContribution(
            issue_id=issue.id,
            issue_key=issue.issue_key,
            title=issue.title,
            issue_type=issue.issue_type,
            current_status=issue.status,
            current_sprint_id=issue.sprint_id,
            current_sprint_name=(sprints_by_id[issue.sprint_id].name if issue.sprint_id in sprints_by_id else None),
            attribution_basis=ContributionAttributionBasis.CURRENT_ASSIGNMENT,
            is_currently_recorded_done=issue.status is IssueStatus.DONE,
        )
        for issue in assigned_issues
    ]

    authored_comments = [
        AuthoredCommentContribution(
            comment_id=comment.id,
            issue_id=comment.issue_id,
            issue_key=issue_keys[comment.issue_id],
            content=comment.content,
            created_at=comment.created_at,
        )
        for comment in sorted(comments, key=lambda comment: (str(comment.created_at), str(comment.id)))
        if comment.employee_id == employee.id and comment.issue_id in issue_keys
    ]
    linked_tests = [
        LinkedTestContribution(
            test_result_id=test.id,
            issue_id=test.issue_id,
            issue_key=issue_keys[test.issue_id],
            link_basis=ContributionLinkBasis.LINKED_TO_CURRENTLY_ASSIGNED_ISSUE,
            testing_status=test.testing_status,
            test_cases_total=test.test_cases_total,
            test_cases_passed=test.test_cases_passed,
            bugs_found=test.bugs_found,
            reopened_count=test.reopened_count,
            testing_notes=test.testing_notes,
            tested_at=test.tested_at,
        )
        for test in sorted(tests, key=lambda test: (issue_keys.get(test.issue_id, ""), str(test.tested_at), str(test.id)))
        if test.issue_id in assigned_issue_ids
    ]
    linked_deployments = [
        LinkedDeploymentContribution(
            deployment_id=deployment.id,
            issue_id=deployment.issue_id,
            issue_key=issue_keys[deployment.issue_id],
            link_basis=ContributionLinkBasis.LINKED_TO_CURRENTLY_ASSIGNED_ISSUE,
            deployment_status=deployment.deployment_status,
            environment=deployment.environment,
            deployment_date=deployment.deployment_date,
            production_notes=deployment.production_notes,
            production_incidents=deployment.production_incidents,
        )
        for deployment in sorted(
            deployments,
            key=lambda deployment: (
                issue_keys.get(deployment.issue_id, ""),
                str(deployment.deployment_date),
                str(deployment.id),
            ),
        )
        if deployment.issue_id in assigned_issue_ids
    ]

    connections: list[ExplicitRequirementConnection] = []
    canonical_context: list[CanonicalRequirementDocumentContext] = []
    connected_requirement_ids: set[UUID] = set()
    for link in sorted(
        requirement_trace_links,
        key=lambda link: (
            requirements_by_id.get(link.requirement_id).requirement_key
            if requirements_by_id.get(link.requirement_id) is not None
            else "",
            issue_keys.get(link.issue_id, ""),
            str(link.id),
        ),
    ):
        if (
            link.project_id != project.id
            or
            link.link_kind is not RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE
            or link.issue_id not in assigned_issue_ids
        ):
            continue
        requirement = requirements_by_id.get(link.requirement_id)
        if requirement is None or requirement.project_id != project.id:
            continue
        connected_requirement_ids.add(requirement.id)
        connections.append(
            ExplicitRequirementConnection(
                requirement_id=requirement.id,
                requirement_key=requirement.requirement_key,
                requirement_statement=requirement.statement,
                issue_id=link.issue_id,
                issue_key=issue_keys[link.issue_id],
                trace_link_id=link.id,
                trace_link_kind=link.link_kind,
                connection_basis=ContributionLinkBasis.EXPLICIT_REQUIREMENT_TRACE,
                trace_verification=TraceVerificationMetadata(
                    verified_by_id=link.verified_by_id,
                    verified_at=link.verified_at,
                ),
            )
        )
    for requirement_id in sorted(
        connected_requirement_ids,
        key=lambda item: (requirements_by_id[item].requirement_key, str(item)),
    ):
        requirement = requirements_by_id[requirement_id]
        source = canonical_sources_by_requirement_id.get(requirement_id)
        if source is None:
            continue
        chunk, document = source
        canonical_context.append(
            CanonicalRequirementDocumentContext(
                requirement_id=requirement.id,
                requirement_key=requirement.requirement_key,
                source_chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                document_type=document.document_type,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.content,
                context_basis=ContributionLinkBasis.CANONICAL_REQUIREMENT_SOURCE,
            )
        )

    current_sprint_ids = sorted(
        {issue.sprint_id for issue in assigned_issues if issue.sprint_id in sprints_by_id},
        key=lambda sprint_id: (
            str(sprints_by_id[sprint_id].start_date),
            sprints_by_id[sprint_id].name,
            str(sprint_id),
        ),
    )
    sprint_context = [
        CurrentSprintContext(
            id=sprint_id,
            name=sprints_by_id[sprint_id].name,
            status=sprints_by_id[sprint_id].status.value,
        )
        for sprint_id in current_sprint_ids
    ]
    return EmployeeContributionReport(
        employee=ContributionEmployee(
            id=employee.id, employee_code=employee.employee_code, name=employee.name,
            role=employee.role, department=employee.department,
        ),
        project=ContributionProject(id=project.id, project_key=project.project_key, name=project.name),
        scope=_scope(sprint),
        currently_assigned_issues=assigned_records,
        currently_assigned_issue_keys_recorded_done=[
            item.issue_key for item in assigned_records if item.is_currently_recorded_done
        ],
        current_sprint_context=sprint_context,
        authored_comments=authored_comments,
        linked_test_evidence=linked_tests,
        linked_deployment_evidence=linked_deployments,
        explicit_requirement_connections=connections,
        canonical_requirement_document_context=canonical_context,
        evidence_coverage=ContributionEvidenceCoverage(
            current_assignment_issue_count=len(assigned_issues),
            current_assignment_issue_records_included=len(assigned_records),
            authored_comment_count=len(authored_comments),
            linked_test_evidence_count=len(linked_tests),
            linked_deployment_evidence_count=len(linked_deployments),
            explicit_requirement_connection_count=len(connections),
            canonical_requirement_document_context_count=len(canonical_context),
            count_bounded=False,
        ),
        limitations=_limitations(sprint=sprint),
    )


def _scope(sprint: Sprint | None) -> ContributionScope:
    if sprint is None:
        return ContributionScope(
            kind="PROJECT",
            sprint_id=None,
            sprint_name=None,
            definition="Currently assigned project issues and project-scoped authored comments.",
        )
    return ContributionScope(
        kind="SPRINT",
        sprint_id=sprint.id,
        sprint_name=sprint.name,
        definition="Currently assigned issues currently associated with the selected sprint and authored comments on that sprint's current issues.",
    )


def _limitations(*, sprint: Sprint | None) -> list[str]:
    limitations = [
        "Current assignment records assignment, not sole implementation, ownership, or employee effort.",
        "A current DONE status does not establish who completed the issue or who was assigned when it became DONE.",
        "Test evidence linked to a currently assigned issue does not establish who performed testing.",
        "Deployment evidence linked to a currently assigned issue does not establish who performed deployment.",
        "Explicit requirement connections do not establish requirement ownership or complete implementation.",
        "Comments establish authorship only, not issue ownership, implementation, or delivery responsibility.",
        "Historical issue reassignment is not represented by the current schema.",
        "This report is not a complete historical 'until now' contribution record.",
    ]
    if sprint is not None:
        limitations.append(
            "Current sprint association is not historical sprint-membership or sprint-movement evidence."
        )
    return limitations
