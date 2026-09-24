"""Deterministic orchestration of existing structured and document evidence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DocumentType
from app.services.document_evidence_service import (
    DocumentEvidenceError,
    DocumentEvidencePackage,
    build_document_evidence_from_intent,
)
from app.services.query_intent_service import (
    QueryIntent,
    QueryIntentError,
    classify_query_intent,
)
from app.services.structured_evidence_service import (
    StructuredEvidenceError,
    StructuredEvidencePackage,
    build_structured_evidence,
)


class HybridEvidenceError(Exception):
    """Controlled error raised while composing existing evidence packages."""

    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


MAX_ISSUE_RETRIEVAL_HINTS = 10
MAX_ISSUE_RETRIEVAL_FIELD_CHARS = 500
MAX_RETRIEVAL_QUESTION_CHARS = 1_200
MAX_AUGMENTED_RETRIEVAL_QUERY_CHARS = 6_000


@dataclass(frozen=True)
class HybridEvidencePackage:
    query: str
    project_key: str
    intent: QueryIntent
    needs_structured_evidence: bool
    needs_document_evidence: bool
    employee_reference: str | None
    sprint_reference: str | None
    requested_document_types: list[DocumentType]
    structured_evidence: StructuredEvidencePackage | None
    document_evidence: DocumentEvidencePackage | None
    warnings: list[str]


def _deduplicate_warnings(*warning_groups: list[str]) -> list[str]:
    warnings: list[str] = []
    for group in warning_groups:
        for warning in group:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _truncate_retrieval_text(value: object, limit: int) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _append_retrieval_line(lines: list[str], line: str) -> bool:
    candidate = "\n".join([*lines, line])
    if len(candidate) > MAX_AUGMENTED_RETRIEVAL_QUERY_CHARS:
        return False
    lines.append(line)
    return True


def _parent_issue_hint(issue: object) -> str:
    key = _truncate_retrieval_text(
        getattr(issue, "parent_issue_key", None), MAX_ISSUE_RETRIEVAL_FIELD_CHARS
    )
    title = _truncate_retrieval_text(
        getattr(issue, "parent_issue_title", None), MAX_ISSUE_RETRIEVAL_FIELD_CHARS
    )
    if key and title:
        return f"{key} — {title}"
    return key or title


def _build_issue_aware_retrieval_query(
    query: str,
    structured_evidence: StructuredEvidencePackage,
) -> str | None:
    """Build one bounded semantic hint from already selected employee issue facts."""
    issues = list(getattr(structured_evidence, "issues", []))
    if not issues:
        return None

    lines = [
        "QUESTION",
        _truncate_retrieval_text(query, MAX_RETRIEVAL_QUESTION_CHARS),
        "",
        "ASSIGNED ISSUE CONTEXT FOR RETRIEVAL",
    ]
    # The structured issue query has no database ordering guarantee. This order is
    # used only for the private retrieval hint; retained evidence is not reordered.
    ordered_issues = sorted(
        issues,
        key=lambda issue: (
            _truncate_retrieval_text(getattr(issue, "issue_key", None), MAX_ISSUE_RETRIEVAL_FIELD_CHARS),
            str(getattr(issue, "id", "")),
        ),
    )
    for issue in ordered_issues[:MAX_ISSUE_RETRIEVAL_HINTS]:
        issue_key = _truncate_retrieval_text(
            getattr(issue, "issue_key", None), MAX_ISSUE_RETRIEVAL_FIELD_CHARS
        )
        title = _truncate_retrieval_text(
            getattr(issue, "title", None), MAX_ISSUE_RETRIEVAL_FIELD_CHARS
        )
        if not _append_retrieval_line(lines, f"- {issue_key}: {title}"):
            break
        for label, value in (
            ("Description", getattr(issue, "description", None)),
            ("Acceptance criteria", getattr(issue, "acceptance_criteria", None)),
            ("Technical notes", getattr(issue, "technical_notes", None)),
            ("Parent issue", _parent_issue_hint(issue)),
        ):
            text = _truncate_retrieval_text(value, MAX_ISSUE_RETRIEVAL_FIELD_CHARS)
            if text and not _append_retrieval_line(lines, f"  {label}: {text}"):
                return "\n".join(lines)
    return "\n".join(lines)


def _issue_aware_retrieval_query(
    intent_result: object,
    structured_evidence: StructuredEvidencePackage | None,
) -> str | None:
    """Enable issue-aware hints only for explicit employee feature-context queries."""
    if (
        structured_evidence is None
        or not getattr(structured_evidence, "employee_scope_active", False)
        or getattr(intent_result, "intent", None) is not QueryIntent.HYBRID
        or not getattr(intent_result, "employee_reference", None)
        or "employee_feature_context" not in getattr(intent_result, "matched_signals", [])
    ):
        return None
    return _build_issue_aware_retrieval_query(intent_result.query, structured_evidence)


def build_hybrid_evidence(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int = 5,
) -> HybridEvidencePackage:
    """Classify once, invoke only required existing evidence branches, and merge facts."""
    try:
        intent_result = classify_query_intent(query)
    except QueryIntentError as error:
        raise HybridEvidenceError(error.args[0], status_code=422) from error
    except Exception as error:
        raise HybridEvidenceError("Unable to classify intelligence query") from error

    structured_evidence: StructuredEvidencePackage | None = None
    document_evidence: DocumentEvidencePackage | None = None
    try:
        if intent_result.needs_structured_evidence:
            structured_evidence = build_structured_evidence(
                db,
                project_key,
                employee_reference=intent_result.employee_reference,
                sprint_reference=intent_result.sprint_reference,
            )
        if intent_result.needs_document_evidence:
            retrieval_query = _issue_aware_retrieval_query(intent_result, structured_evidence)
            if retrieval_query is None:
                document_evidence = build_document_evidence_from_intent(
                    db,
                    project_key,
                    intent_result,
                    top_k=top_k,
                )
            else:
                document_evidence = build_document_evidence_from_intent(
                    db,
                    project_key,
                    intent_result,
                    top_k=top_k,
                    retrieval_query=retrieval_query,
                )
    except StructuredEvidenceError as error:
        raise HybridEvidenceError(error.detail, status_code=error.status_code) from error
    except DocumentEvidenceError as error:
        raise HybridEvidenceError(error.detail, status_code=error.status_code) from error
    except HybridEvidenceError:
        raise
    except Exception as error:
        raise HybridEvidenceError("Unable to build hybrid evidence") from error

    return HybridEvidencePackage(
        query=intent_result.query,
        project_key=project_key,
        intent=intent_result.intent,
        needs_structured_evidence=intent_result.needs_structured_evidence,
        needs_document_evidence=intent_result.needs_document_evidence,
        employee_reference=intent_result.employee_reference,
        sprint_reference=intent_result.sprint_reference,
        requested_document_types=intent_result.document_types,
        structured_evidence=structured_evidence,
        document_evidence=document_evidence,
        warnings=_deduplicate_warnings(
            structured_evidence.warnings if structured_evidence is not None else [],
            document_evidence.warnings if document_evidence is not None else [],
        ),
    )
