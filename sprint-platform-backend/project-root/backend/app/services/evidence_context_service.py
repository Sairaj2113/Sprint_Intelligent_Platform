"""Deterministic category-count budgeting for already cited evidence packages."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.document_evidence_service import DocumentEvidenceItem
from app.services.evidence_source_service import (
    CitedEvidencePackage,
    EvidenceSource,
    EvidenceSourceError,
    EvidenceSourceType,
    build_cited_evidence,
)
from app.services.query_intent_service import QueryIntent
from app.services.structured_evidence_service import (
    StructuredCommentEvidence,
    StructuredDeploymentEvidence,
    StructuredIssueEvidence,
    StructuredTestEvidence,
)


class EvidenceContextError(Exception):
    """Controlled error raised while preparing a bounded evidence context."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class EvidenceContextLimits:
    max_issues: int = 20
    max_tests: int = 10
    max_deployments: int = 10
    max_comments: int = 10
    max_documents: int = 5

    def __post_init__(self) -> None:
        limits = {
            "max_issues": self.max_issues,
            "max_tests": self.max_tests,
            "max_deployments": self.max_deployments,
            "max_comments": self.max_comments,
            "max_documents": self.max_documents,
        }
        upper_bounds = {
            "max_issues": 100,
            "max_tests": 100,
            "max_deployments": 100,
            "max_comments": 100,
            "max_documents": 20,
        }
        for name, value in limits.items():
            if not isinstance(value, int) or value < 0:
                raise EvidenceContextError(f"{name} must be an integer greater than or equal to zero")
            if value > upper_bounds[name]:
                raise EvidenceContextError(f"{name} exceeds the maximum allowed limit")


DEFAULT_EVIDENCE_CONTEXT_LIMITS = EvidenceContextLimits()


@dataclass(frozen=True)
class EvidenceContextStats:
    available_issues: int
    included_issues: int
    omitted_issues: int
    available_tests: int
    included_tests: int
    omitted_tests: int
    available_deployments: int
    included_deployments: int
    omitted_deployments: int
    available_comments: int
    included_comments: int
    omitted_comments: int
    available_documents: int
    included_documents: int
    omitted_documents: int
    available_sources: int
    included_sources: int
    truncated: bool


@dataclass(frozen=True)
class BoundedEvidenceContext:
    query: str
    project_key: str
    intent: QueryIntent
    employee_reference: str | None
    sprint_reference: str | None
    issues: list[StructuredIssueEvidence]
    tests: list[StructuredTestEvidence]
    deployments: list[StructuredDeploymentEvidence]
    comments: list[StructuredCommentEvidence]
    documents: list[DocumentEvidenceItem]
    sources: list[EvidenceSource]
    stats: EvidenceContextStats
    warnings: list[str]


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))


def _filter_sources(
    sources: list[EvidenceSource],
    *,
    issue_ids: set[UUID],
    test_ids: set[UUID],
    deployment_ids: set[UUID],
    comment_ids: set[UUID],
    chunk_ids: set[UUID],
) -> list[EvidenceSource]:
    retained: list[EvidenceSource] = []
    for source in sources:
        include = (
            source.source_type == EvidenceSourceType.ISSUE and source.record_id in issue_ids
        ) or (
            source.source_type == EvidenceSourceType.TEST and source.record_id in test_ids
        ) or (
            source.source_type == EvidenceSourceType.DEPLOYMENT and source.record_id in deployment_ids
        ) or (
            source.source_type == EvidenceSourceType.COMMENT and source.record_id in comment_ids
        ) or (
            source.source_type == EvidenceSourceType.DOCUMENT and source.chunk_id in chunk_ids
        )
        if include:
            retained.append(source)
    return retained


def build_bounded_evidence_context(
    cited_evidence: CitedEvidencePackage,
    *,
    limits: EvidenceContextLimits | None = None,
) -> BoundedEvidenceContext:
    """Create a non-mutating, count-bounded view of evidence and matching sources."""
    effective_limits = limits if limits is not None else DEFAULT_EVIDENCE_CONTEXT_LIMITS
    if not isinstance(effective_limits, EvidenceContextLimits):
        raise EvidenceContextError("limits must be an EvidenceContextLimits instance")

    hybrid = cited_evidence.evidence
    structured = hybrid.structured_evidence
    document = hybrid.document_evidence
    available_issues = list(structured.issues) if structured is not None else []
    available_tests = list(structured.tests) if structured is not None else []
    available_deployments = list(structured.deployments) if structured is not None else []
    available_comments = list(structured.comments) if structured is not None else []
    available_documents = list(document.results) if document is not None else []

    issues = available_issues[: effective_limits.max_issues]
    tests = available_tests[: effective_limits.max_tests]
    deployments = available_deployments[: effective_limits.max_deployments]
    comments = available_comments[: effective_limits.max_comments]
    documents = available_documents[: effective_limits.max_documents]
    sources = _filter_sources(
        cited_evidence.sources,
        issue_ids={item.id for item in issues},
        test_ids={item.id for item in tests},
        deployment_ids={item.id for item in deployments},
        comment_ids={item.id for item in comments},
        chunk_ids={item.chunk_id for item in documents},
    )

    counts = (
        len(available_issues), len(issues), len(available_tests), len(tests),
        len(available_deployments), len(deployments), len(available_comments), len(comments),
        len(available_documents), len(documents),
    )
    truncated = any(available > included for available, included in zip(counts[::2], counts[1::2]))
    warnings = list(hybrid.warnings)
    if truncated:
        warnings.append("Evidence context was truncated by configured limits")
    return BoundedEvidenceContext(
        query=hybrid.query,
        project_key=hybrid.project_key,
        intent=hybrid.intent,
        employee_reference=hybrid.employee_reference,
        sprint_reference=hybrid.sprint_reference,
        issues=issues,
        tests=tests,
        deployments=deployments,
        comments=comments,
        documents=documents,
        sources=sources,
        stats=EvidenceContextStats(
            available_issues=len(available_issues), included_issues=len(issues), omitted_issues=len(available_issues) - len(issues),
            available_tests=len(available_tests), included_tests=len(tests), omitted_tests=len(available_tests) - len(tests),
            available_deployments=len(available_deployments), included_deployments=len(deployments), omitted_deployments=len(available_deployments) - len(deployments),
            available_comments=len(available_comments), included_comments=len(comments), omitted_comments=len(available_comments) - len(comments),
            available_documents=len(available_documents), included_documents=len(documents), omitted_documents=len(available_documents) - len(documents),
            available_sources=len(cited_evidence.sources), included_sources=len(sources), truncated=truncated,
        ),
        warnings=_deduplicate_warnings(warnings),
    )


def build_evidence_context(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int = 5,
    limits: EvidenceContextLimits | None = None,
) -> BoundedEvidenceContext:
    """Build cited evidence once, then deterministically prepare a bounded context view."""
    try:
        cited_evidence = build_cited_evidence(db, project_key, query, top_k=top_k)
    except EvidenceSourceError as error:
        raise EvidenceContextError(error.detail, status_code=error.status_code) from error
    except Exception as error:
        raise EvidenceContextError("Unable to build evidence context", status_code=500) from error
    try:
        return build_bounded_evidence_context(cited_evidence, limits=limits)
    except EvidenceContextError:
        raise
    except Exception as error:
        raise EvidenceContextError("Unable to prepare bounded evidence context", status_code=500) from error
