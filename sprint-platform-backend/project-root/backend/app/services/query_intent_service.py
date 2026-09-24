"""Deterministic routing hints for future intelligence queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from app.models import DocumentType


class QueryIntent(str, Enum):
    STRUCTURED = "STRUCTURED"
    DOCUMENT = "DOCUMENT"
    HYBRID = "HYBRID"


class QueryIntentError(Exception):
    """Controlled error raised for an invalid query-intent request."""


STRUCTURED_SIGNALS = (
    "employee",
    "contribution",
    "contribute",
    "contributed",
    "implement",
    "completed",
    "assigned",
    "issue",
    "issues",
    "ticket",
    "sprint",
    "test",
    "tested",
    "deployment",
    "deployed",
    "comment",
    "workflow",
    "kpi",
    "velocity",
    "cycle time",
    "lead time",
    "status",
    "story points",
)

DOCUMENT_SIGNALS = (
    "requirement",
    "requirements",
    "prd",
    "trd",
    "architecture",
    "design",
    "specification",
    "acceptance criteria",
    "release requirement",
    "technical requirement",
    "functional requirement",
    "non-functional requirement",
    "documentation",
)

DOCUMENT_TYPE_PATTERNS: tuple[tuple[DocumentType, tuple[str, ...]], ...] = (
    (DocumentType.PRD, (r"\bprd\b", r"\bproduct requirements?\b")),
    (DocumentType.TRD, (r"\btrd\b", r"\btechnical requirements?\b")),
    (DocumentType.ARCHITECTURE, (r"\barchitecture\b",)),
    (DocumentType.TESTING, (r"\btesting document\b",)),
    (DocumentType.RELEASE, (r"\brelease document\b",)),
    (DocumentType.DESIGN, (r"\bdesign document\b",)),
)

EMPLOYEE_REFERENCE_PATTERNS = (
    r"\bwhat\s+did\s+([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z'-]*)?)\s+(?:contribute|contributed|implement)\b",
    r"\bwhat\s+(?:features?|capabilities|part(?:s)?\s+of\s+the\s+system)\s+did\s+([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z'-]*)?)\s+(?:work\s+on|contribute(?:\s+to)?)\b",
    r"\bcontribution\s+of\s+([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z'-]*)?)\b",
    r"\b(?:issues?|tickets?)\s+(?:were\s+)?assigned\s+to\s+([A-Za-z][A-Za-z0-9]*(?:\s+[A-Za-z][A-Za-z'-]*)?)\b",
    r"\b(?:was\s+)?([A-Za-z][A-Za-z0-9]*)'s\s+sprint\b",
)


EMPLOYEE_CONTEXT_SIGNALS = ("feature", "features", "capability", "capabilities", "system")


@dataclass(frozen=True)
class QueryIntentResult:
    query: str
    intent: QueryIntent
    needs_structured_evidence: bool
    needs_document_evidence: bool
    employee_reference: str | None
    sprint_reference: str | None
    document_types: list[DocumentType]
    matched_signals: list[str]


def _has_signal(query: str, signal: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", query, re.IGNORECASE))


def _matched_signals(query: str, signals: tuple[str, ...]) -> list[str]:
    return [signal for signal in signals if _has_signal(query, signal)]


def _extract_document_types(query: str) -> list[DocumentType]:
    detected: list[DocumentType] = []
    for document_type, patterns in DOCUMENT_TYPE_PATTERNS:
        if any(re.search(pattern, query, re.IGNORECASE) for pattern in patterns):
            detected.append(document_type)
    return detected


def _extract_employee_reference(query: str) -> str | None:
    for pattern in EMPLOYEE_REFERENCE_PATTERNS:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_sprint_reference(query: str) -> str | None:
    match = re.search(r"\bsprint\s+[1-9]\d*\b", query, re.IGNORECASE)
    return match.group(0) if match else None


def _is_employee_context_query(query: str, employee_reference: str | None) -> bool:
    """Identify explicit feature/capability/system questions about one employee."""
    if employee_reference is None:
        return False
    return any(_has_signal(query, signal) for signal in EMPLOYEE_CONTEXT_SIGNALS) or bool(
        re.search(r"\bimplement\b.*\b(?:project|system)\b", query, re.IGNORECASE)
    )


def _evidence_flags(intent: QueryIntent) -> tuple[bool, bool]:
    return (
        intent in (QueryIntent.STRUCTURED, QueryIntent.HYBRID),
        intent in (QueryIntent.DOCUMENT, QueryIntent.HYBRID),
    )


def classify_query_intent(query: str) -> QueryIntentResult:
    """Classify routing needs from explicit lexical signals without retrieving evidence."""
    if not isinstance(query, str) or not query.strip():
        raise QueryIntentError("Query must not be blank")

    employee_reference = _extract_employee_reference(query)
    structured_signals = _matched_signals(query, STRUCTURED_SIGNALS)
    document_signals = _matched_signals(query, DOCUMENT_SIGNALS)
    if _is_employee_context_query(query, employee_reference):
        if not structured_signals:
            structured_signals.append("employee_contribution_context")
        document_signals.append("employee_feature_context")
    matched_signals = [*structured_signals, *document_signals]

    if structured_signals and document_signals:
        intent = QueryIntent.HYBRID
    elif structured_signals:
        intent = QueryIntent.STRUCTURED
    elif document_signals:
        intent = QueryIntent.DOCUMENT
    else:
        intent = QueryIntent.HYBRID
        matched_signals.append("default_hybrid")

    needs_structured_evidence, needs_document_evidence = _evidence_flags(intent)
    return QueryIntentResult(
        query=query,
        intent=intent,
        needs_structured_evidence=needs_structured_evidence,
        needs_document_evidence=needs_document_evidence,
        employee_reference=employee_reference,
        sprint_reference=_extract_sprint_reference(query),
        document_types=_extract_document_types(query),
        matched_signals=matched_signals,
    )
