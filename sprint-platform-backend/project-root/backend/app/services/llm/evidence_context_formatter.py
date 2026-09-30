"""Deterministic plain-text formatting of an already bounded evidence context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from app.services.evidence_context_service import BoundedEvidenceContext


@dataclass(frozen=True)
class FormattedEvidenceContext:
    """Provider-neutral plain text and source labels for a later LLM consumer."""

    text: str
    source_ids: tuple[str, ...]
    truncated: bool


def format_evidence_context(context: BoundedEvidenceContext) -> FormattedEvidenceContext:
    """Format preselected evidence without I/O, retrieval, inference, or validation."""
    source_ids = tuple(source.source_id for source in context.sources)
    lines = [
        "PROJECT CONTEXT",
        f"Question: {_value(context.query)}",
        f"Project key: {_value(context.project_key)}",
        f"Intent: {_value(context.intent)}",
    ]
    _append_optional(lines, "Employee reference", context.employee_reference)
    _append_optional(lines, "Sprint reference", context.sprint_reference)
    sprint_references = getattr(context, "sprint_references", ())
    if sprint_references:
        _append_optional(lines, "Sprint references", ", ".join(sprint_references))

    lines.extend(_format_employee_performance(context))

    if _uses_requirement_delivery_grouping(context):
        lines.extend(_format_requirement_delivery(context))
    else:
        # Preserve the established non-traceability presentation exactly for
        # contexts that did not select verified requirement evidence.
        lines.extend(_format_requirements(context.requirements, context.sources))
        lines.extend(_format_trace_links(context.trace_links, context.sources))
    lines.extend(_format_issues(context.issues, context.sources))
    lines.extend(_format_tests(context.tests, context.sources))
    lines.extend(_format_deployments(context.deployments, context.sources))
    lines.extend(_format_comments(context.comments, context.sources))
    lines.extend(_format_documents(context.documents, context.sources))
    lines.extend(_format_status(context.stats, getattr(context, "coverage", None)))
    lines.extend(_format_warnings(context.warnings))
    return FormattedEvidenceContext(
        text="\n".join(lines),
        source_ids=source_ids,
        truncated=context.stats.truncated,
    )


def _format_employee_performance(context: BoundedEvidenceContext) -> list[str]:
    """Render one deterministic KPI record without replacing raw evidence."""
    report = getattr(context, "employee_performance", None)
    if report is None:
        return []
    source = next(
        (item for item in context.sources if _source_type(item) == "KPI"),
        None,
    )
    lines = ["", "EMPLOYEE PERFORMANCE EVIDENCE"]
    _append_optional(lines, "Citation ID", getattr(source, "source_id", None))
    _append_optional(lines, "Employee code", report.employee.employee_code)
    _append_optional(lines, "Employee name", report.employee.name)
    _append_optional(lines, "Project key", report.project.project_key)
    _append_optional(lines, "Scope kind", report.scope.kind)
    _append_optional(lines, "Scope sprint", report.scope.sprint_name)
    _append_optional(lines, "Scope definition", report.scope.definition)

    delivery = report.delivery
    lines.append(
        "Delivery metrics: "
        f"assigned issues={delivery.assigned_issue_count}; "
        f"completed issues={delivery.completed_issue_count}; "
        f"completion-rate eligible issues={delivery.completion_rate_eligible_issue_count}"
    )
    if delivery.completion_rate_percentage is not None:
        _append_optional(lines, "Completion rate percentage", delivery.completion_rate_percentage)
    lines.append(
        "Story-point and bug metrics: "
        f"assigned story points={delivery.assigned_story_points}; "
        f"completed story points={delivery.completed_story_points}; "
        f"assigned bugs={delivery.assigned_bug_count}; "
        f"resolved bugs={delivery.resolved_bug_count}"
    )
    distribution = delivery.status_distribution
    lines.append(
        "Issue status distribution: "
        f"BACKLOG={distribution.backlog}; "
        f"SELECTED_FOR_SPRINT={distribution.selected_for_sprint}; "
        f"TODO={distribution.todo}; IN_PROGRESS={distribution.in_progress}; "
        f"CODE_REVIEW={distribution.code_review}; TESTING={distribution.testing}; "
        f"READY_FOR_RELEASE={distribution.ready_for_release}; DONE={distribution.done}"
    )

    quality = report.quality
    lines.append(
        "Quality evidence: "
        f"completed assigned issues={quality.completed_assigned_issue_count}; "
        f"completed with test evidence={quality.completed_issues_with_test_evidence}; "
        f"completed without test evidence={quality.completed_issues_without_test_evidence}; "
        f"linked test records={quality.linked_test_result_count}; "
        f"valid test-case records={quality.test_records_with_valid_case_counts}; "
        f"test cases passed={quality.test_cases_passed}/{quality.test_cases_total}"
    )
    if quality.test_case_pass_rate_percentage is not None:
        _append_optional(lines, "Test-case pass rate percentage", quality.test_case_pass_rate_percentage)

    deployments = report.deployment_evidence
    lines.append(
        "Deployment evidence: "
        f"assigned issues with deployment evidence={deployments.assigned_issues_with_deployment_evidence}; "
        f"deployment records={deployments.deployment_record_count}; "
        f"NOT_DEPLOYED={deployments.not_deployed_count}; STAGING={deployments.staging_count}; "
        f"PRODUCTION={deployments.production_count}; FAILED={deployments.failed_count}; "
        f"records without environment={deployments.deployments_without_recorded_environment}"
    )
    if deployments.environment_counts:
        _append_optional(
            lines,
            "Deployment environments",
            ", ".join(
                f"{environment}={count}"
                for environment, count in deployments.environment_counts.items()
            ),
        )

    requirement_connections = report.requirement_connections
    lines.append(
        "Explicit requirement connections: "
        f"IMPLEMENTED_BY_ISSUE links={requirement_connections.explicit_implemented_requirement_link_count}"
    )
    if requirement_connections.explicit_implemented_requirement_keys:
        _append_optional(
            lines,
            "Explicit implemented requirement keys",
            ", ".join(requirement_connections.explicit_implemented_requirement_keys),
        )
    activity = report.documented_activity
    lines.append(
        "Documented activity: "
        f"authored comments={activity.authored_comment_count}; "
        f"issues commented on={activity.issues_commented_on_count}"
    )
    timing = report.lifecycle_timing
    for label, eligible, average in (
        ("Cycle time", timing.cycle_time_eligible_issue_count, timing.average_cycle_time_hours),
        ("Development time", timing.development_time_eligible_issue_count, timing.average_development_time_hours),
        ("Review time", timing.review_time_eligible_issue_count, timing.average_review_time_hours),
        ("Testing time", timing.testing_time_eligible_issue_count, timing.average_testing_time_hours),
    ):
        _append_optional(lines, f"{label} eligible issue count", eligible)
        if average is not None:
            _append_optional(lines, f"Average {label.lower()} hours", average)
    lines.append("Performance evidence limitations:")
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    return lines


def _uses_requirement_delivery_grouping(context: BoundedEvidenceContext) -> bool:
    """Use grouping only for the existing verified-traceability route."""
    coverage = getattr(context, "coverage", None)
    requirements = getattr(coverage, "requirements", None)
    trace_links = getattr(coverage, "trace_links", None)
    return bool(
        getattr(requirements, "selected", False)
        or getattr(trace_links, "selected", False)
        or context.requirements
        or context.trace_links
    )


def _format_requirement_delivery(context: BoundedEvidenceContext) -> list[str]:
    """Render only explicit, final-context requirement-to-delivery joins.

    The joins use persisted IDs already present in the bounded context.  They
    perform no I/O and never infer a relationship from an issue, test, or
    deployment that lacks an explicit retained trace link.
    """
    lines = ["", "VERIFIED REQUIREMENT DELIVERY EVIDENCE"]
    if not context.requirements:
        return [*lines, "- No verified requirement evidence."]

    traces_by_requirement: dict[object, list[Any]] = {}
    for trace in context.trace_links:
        traces_by_requirement.setdefault(trace.requirement_id, []).append(trace)
    issues_by_id = {item.id: item for item in context.issues}
    tests_by_id = {item.id: item for item in context.tests}
    deployments_by_id = {item.id: item for item in context.deployments}

    for requirement in context.requirements:
        requirement_source = _source_for_record(context.sources, "REQUIREMENT", requirement.id)
        _append_optional(lines, "- Requirement citation ID", getattr(requirement_source, "source_id", None))
        _append_optional(lines, "  Requirement key", requirement.requirement_key)
        _append_optional(lines, "  Requirement statement", requirement.statement)

        requirement_traces = traces_by_requirement.get(requirement.id, [])
        if not requirement_traces:
            lines.append("  Verified supporting relationships: none supplied.")
            continue
        lines.append("  Verified supporting relationships:")
        for trace in requirement_traces:
            _append_trace_relationship(
                lines,
                trace,
                context.sources,
                issues_by_id,
                tests_by_id,
                deployments_by_id,
            )
    return lines


def _append_trace_relationship(
    lines: list[str],
    trace: Any,
    sources: list[Any],
    issues_by_id: dict[object, Any],
    tests_by_id: dict[object, Any],
    deployments_by_id: dict[object, Any],
) -> None:
    """Append one stored trace and, only when retained, its exact target data."""
    trace_source = _source_for_record(sources, "TRACEABILITY", trace.id)
    _append_optional(lines, "  - Trace citation ID", getattr(trace_source, "source_id", None))
    relationship = " → ".join(
        value
        for value in (_value(trace.link_kind), _value(trace.target_label))
        if value
    )
    _append_optional(lines, "    Explicit relationship", relationship)

    target_type = _value(trace.target_type).upper()
    if target_type == "ISSUE":
        issue = issues_by_id.get(trace.target_id)
        source = _source_for_record(sources, "ISSUE", trace.target_id)
        if issue is not None and source is not None:
            issue_summary = " | ".join(
                value
                for value in (_value(issue.issue_key), _value(issue.status), _value(issue.title))
                if value
            )
            _append_optional(lines, f"    Issue evidence citation ID {source.source_id}", issue_summary)
    elif target_type == "TEST":
        test = tests_by_id.get(trace.target_id)
        source = _source_for_record(sources, "TEST", trace.target_id)
        if test is not None and source is not None:
            case_counts = " / ".join(
                value
                for value in (_value(test.test_cases_passed), _value(test.test_cases_total))
                if value
            )
            test_summary = " | ".join(
                value
                for value in (
                    _value(test.testing_status),
                    f"{case_counts} test cases passed" if case_counts else "",
                )
                if value
            )
            _append_optional(lines, f"    Test evidence citation ID {source.source_id}", test_summary)
    elif target_type == "DEPLOYMENT":
        deployment = deployments_by_id.get(trace.target_id)
        source = _source_for_record(sources, "DEPLOYMENT", trace.target_id)
        if deployment is not None and source is not None:
            deployment_summary = " | ".join(
                value
                for value in (
                    _value(deployment.deployment_status),
                    _value(deployment.environment),
                    _value(deployment.deployment_date),
                )
                if value
            )
            _append_optional(lines, f"    Deployment evidence citation ID {source.source_id}", deployment_summary)


def _format_requirements(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "VERIFIED REQUIREMENTS"]
    if not items:
        return [*lines, "- No verified requirement evidence."]
    for item in items:
        source = _source_for_record(sources, "REQUIREMENT", item.id)
        _append_optional(lines, "- Citation ID", getattr(source, "source_id", None))
        _append_optional(lines, "  Requirement key", item.requirement_key)
        _append_optional(lines, "  Requirement statement", item.statement)
        _append_optional(lines, "  Canonical document", item.document_title)
        _append_optional(lines, "  Source chunk index", item.chunk_index)
        _append_optional(lines, "  Source section", item.section_title)
    return lines


def _format_trace_links(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "VERIFIED TRACEABILITY"]
    if not items:
        return [*lines, "- No verified trace links."]
    for item in items:
        source = _source_for_record(sources, "TRACEABILITY", item.id)
        _append_optional(lines, "- Citation ID", getattr(source, "source_id", None))
        _append_optional(lines, "  Requirement key", item.requirement_key)
        _append_optional(lines, "  Verified relationship kind", item.link_kind)
        _append_optional(lines, "  Explicit target type", item.target_type)
        _append_optional(lines, "  Explicit target", item.target_label)
    return lines


def _format_issues(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "ISSUES"]
    if not items:
        return [*lines, "- No issue evidence."]
    for item in items:
        source = _source_for_record(sources, "ISSUE", item.id, issue_key=item.issue_key)
        heading = _with_source(source, f"{_value(item.issue_key)} | {_value(item.issue_type)} | {_value(item.status)}")
        lines.append(f"- {heading}")
        _append_optional(lines, "  Title", item.title)
        _append_optional(lines, "  Story points", item.story_points)
        _append_optional(lines, "  Assignee", item.assignee_name)
        _append_optional(lines, "  Sprint", item.sprint_name)
        _append_optional(lines, "  Description", getattr(item, "description", None))
        _append_optional(lines, "  Acceptance criteria", getattr(item, "acceptance_criteria", None))
        _append_optional(lines, "  Technical notes", getattr(item, "technical_notes", None))
        _append_optional(lines, "  Parent issue", _parent_issue_label(item))
        _append_optional(lines, "  Created at", item.created_at)
        _append_optional(lines, "  Completed at", item.completed_at)
    return lines


def _format_tests(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "TESTS"]
    if not items:
        return [*lines, "- No test evidence."]
    for item in items:
        source = _source_for_record(sources, "TEST", item.id)
        heading = _with_source(source, f"Issue ID: {_value(item.issue_id)} | {_value(item.testing_status)}")
        lines.append(f"- {heading}")
        _append_optional(lines, "  Issue key", getattr(source, "issue_key", None))
        _append_optional(lines, "  Test cases total", item.test_cases_total)
        _append_optional(lines, "  Test cases passed", item.test_cases_passed)
        _append_optional(lines, "  Bugs found", item.bugs_found)
        _append_optional(lines, "  Reopened count", item.reopened_count)
        _append_optional(lines, "  Tested by", item.tested_by_name)
        _append_optional(lines, "  Tested at", item.tested_at)
        _append_optional(lines, "  Testing notes", getattr(item, "testing_notes", None))
    return lines


def _format_deployments(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "DEPLOYMENTS"]
    if not items:
        return [*lines, "- No deployment evidence."]
    for item in items:
        source = _source_for_record(sources, "DEPLOYMENT", item.id)
        heading = _with_source(source, f"Issue ID: {_value(item.issue_id)} | {_value(item.deployment_status)}")
        lines.append(f"- {heading}")
        _append_optional(lines, "  Issue key", getattr(source, "issue_key", None))
        _append_optional(lines, "  Environment", item.environment)
        _append_optional(lines, "  Deployment date", item.deployment_date)
        _append_optional(lines, "  Production notes", item.production_notes)
        _append_optional(lines, "  Production incidents", item.production_incidents)
    return lines


def _format_comments(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "COMMENTS"]
    if not items:
        return [*lines, "- No comment evidence."]
    for item in items:
        source = _source_for_record(sources, "COMMENT", item.id)
        heading = _with_source(source, f"Issue ID: {_value(item.issue_id)}")
        lines.append(f"- {heading}")
        _append_optional(lines, "  Issue key", getattr(source, "issue_key", None))
        _append_optional(lines, "  Employee", item.employee_name)
        _append_optional(lines, "  Created at", item.created_at)
        _append_optional(lines, "  Content", item.content)
    return lines


def _format_documents(items: list[Any], sources: list[Any]) -> list[str]:
    lines = ["", "DOCUMENT EVIDENCE"]
    if not items:
        return [*lines, "- No document evidence."]
    # The input list is already ordered by semantic retrieval.  Do not sort it.
    for item in items:
        source = _source_for_document(sources, item)
        heading = _with_source(source, f"{_value(item.document_title)} | {_value(item.document_type)}")
        lines.append(f"- {heading}")
        _append_optional(lines, "  Chunk index", item.chunk_index)
        _append_optional(lines, "  Page number", item.page_number)
        _append_optional(lines, "  Section title", item.section_title)
        _append_optional(lines, "  Content", item.content)
    return lines


def _format_status(stats: Any, coverage: Any | None) -> list[str]:
    lines = [
        "",
        "CONTEXT STATUS",
        f"- Issues: {stats.included_issues} included, {stats.omitted_issues} omitted, {stats.available_issues} available",
        f"- Tests: {stats.included_tests} included, {stats.omitted_tests} omitted, {stats.available_tests} available",
        f"- Deployments: {stats.included_deployments} included, {stats.omitted_deployments} omitted, {stats.available_deployments} available",
        f"- Comments: {stats.included_comments} included, {stats.omitted_comments} omitted, {stats.available_comments} available",
        f"- Documents: {stats.included_documents} included, {stats.omitted_documents} omitted, {stats.available_documents} available",
        f"- Requirements: {stats.included_requirements} included, {stats.omitted_requirements} omitted, {stats.available_requirements} available",
        f"- Verified trace links: {stats.included_trace_links} included, {stats.omitted_trace_links} omitted, {stats.available_trace_links} available",
        f"- Sources: {stats.included_sources} included, {stats.available_sources} available",
        f"- Truncated: {str(stats.truncated).lower()}",
    ]
    if coverage is not None:
        lines.append(f"- Selected evidence scope: {_value(coverage.selected_scope)}")
        for label, category in (
            ("Issue evidence", coverage.issues),
            ("Test evidence", coverage.tests),
            ("Deployment evidence", coverage.deployments),
            ("Comment evidence", coverage.comments),
            ("Document retrieval results", coverage.documents),
            ("Verified requirements", coverage.requirements),
            ("Verified trace links", coverage.trace_links),
        ):
            if not category.selected:
                state = "not selected"
            else:
                state = "complete after bounds" if category.complete else "incomplete after bounds"
            lines.append(f"- {label}: {state}")
    return lines


def _format_warnings(warnings: list[str]) -> list[str]:
    lines = ["", "WARNINGS"]
    if not warnings:
        return [*lines, "- No warnings."]
    return [*lines, *[f"- {_value(warning)}" for warning in warnings]]


def _source_for_record(sources: list[Any], source_type: str, record_id: object, *, issue_key: str | None = None) -> Any | None:
    for source in sources:
        if _source_type(source) == source_type and source.record_id == record_id:
            return source
    if issue_key is not None:
        for source in sources:
            if _source_type(source) == source_type and source.issue_key == issue_key:
                return source
    return None


def _source_for_document(sources: list[Any], item: Any) -> Any | None:
    for source in sources:
        if _source_type(source) == "DOCUMENT" and source.chunk_id == item.chunk_id:
            return source
    for source in sources:
        if (
            _source_type(source) == "DOCUMENT"
            and source.document_id == item.document_id
            and source.chunk_index == item.chunk_index
        ):
            return source
    return None


def _source_type(source: Any) -> str:
    value = getattr(source, "source_type", None)
    return value.value if isinstance(value, Enum) else value if isinstance(value, str) else ""


def _with_source(source: Any | None, text: str) -> str:
    source_id = getattr(source, "source_id", None)
    return f"[{source_id}] {text}" if isinstance(source_id, str) and source_id else text


def _parent_issue_label(item: Any) -> str | None:
    """Render only the explicitly supplied parent identity and title."""
    key = _value(getattr(item, "parent_issue_key", None))
    title = _value(getattr(item, "parent_issue_title", None))
    if key and title:
        return f"{key} — {title}"
    return key or title or None


def _append_optional(lines: list[str], label: str, value: object) -> None:
    rendered = _value(value)
    if rendered:
        lines.append(f"{label}: {rendered}")


def _value(value: object) -> str:
    """Render only known scalar contract values; omit unexpected internal objects."""
    if value is None:
        return ""
    if isinstance(value, Enum):
        return _value(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return str(value)
    return ""
