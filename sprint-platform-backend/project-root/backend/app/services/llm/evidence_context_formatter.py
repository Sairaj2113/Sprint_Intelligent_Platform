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

    lines.extend(_format_issues(context.issues, context.sources))
    lines.extend(_format_tests(context.tests, context.sources))
    lines.extend(_format_deployments(context.deployments, context.sources))
    lines.extend(_format_comments(context.comments, context.sources))
    lines.extend(_format_documents(context.documents, context.sources))
    lines.extend(_format_status(context.stats))
    lines.extend(_format_warnings(context.warnings))
    return FormattedEvidenceContext(
        text="\n".join(lines),
        source_ids=source_ids,
        truncated=context.stats.truncated,
    )


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


def _format_status(stats: Any) -> list[str]:
    return [
        "",
        "CONTEXT STATUS",
        f"- Issues: {stats.included_issues} included, {stats.omitted_issues} omitted, {stats.available_issues} available",
        f"- Tests: {stats.included_tests} included, {stats.omitted_tests} omitted, {stats.available_tests} available",
        f"- Deployments: {stats.included_deployments} included, {stats.omitted_deployments} omitted, {stats.available_deployments} available",
        f"- Comments: {stats.included_comments} included, {stats.omitted_comments} omitted, {stats.available_comments} available",
        f"- Documents: {stats.included_documents} included, {stats.omitted_documents} omitted, {stats.available_documents} available",
        f"- Sources: {stats.included_sources} included, {stats.available_sources} available",
        f"- Truncated: {str(stats.truncated).lower()}",
    ]


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
