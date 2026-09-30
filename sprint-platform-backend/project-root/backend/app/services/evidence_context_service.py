"""Deterministic category-count budgeting for already cited evidence packages."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    StructuredRequirementEvidence,
    StructuredTestEvidence,
    StructuredTraceLinkEvidence,
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
    max_requirements: int = 20
    max_trace_links: int = 30

    def __post_init__(self) -> None:
        limits = {
            "max_issues": self.max_issues,
            "max_tests": self.max_tests,
            "max_deployments": self.max_deployments,
            "max_comments": self.max_comments,
            "max_documents": self.max_documents,
            "max_requirements": self.max_requirements,
            "max_trace_links": self.max_trace_links,
        }
        upper_bounds = {
            "max_issues": 100,
            "max_tests": 100,
            "max_deployments": 100,
            "max_comments": 100,
            "max_documents": 20,
            "max_requirements": 100,
            "max_trace_links": 100,
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
    available_requirements: int = 0
    included_requirements: int = 0
    omitted_requirements: int = 0
    available_trace_links: int = 0
    included_trace_links: int = 0
    omitted_trace_links: int = 0


@dataclass(frozen=True)
class EvidenceCategoryCoverage:
    """Bounded-retention completeness for one selected evidence category."""

    selected: bool
    available: int
    included: int
    omitted: int
    complete: bool | None


@dataclass(frozen=True)
class EvidenceCoverage:
    """Explicit scope and per-category completeness for the bounded context."""

    selected_scope: str
    issues: EvidenceCategoryCoverage
    tests: EvidenceCategoryCoverage
    deployments: EvidenceCategoryCoverage
    comments: EvidenceCategoryCoverage
    documents: EvidenceCategoryCoverage
    requirements: EvidenceCategoryCoverage = field(
        default_factory=lambda: EvidenceCategoryCoverage(False, 0, 0, 0, None)
    )
    trace_links: EvidenceCategoryCoverage = field(
        default_factory=lambda: EvidenceCategoryCoverage(False, 0, 0, 0, None)
    )


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
    coverage: EvidenceCoverage
    sprint_references: tuple[str, ...] = ()
    multi_sprint_comparison: bool = False
    requires_complete_evidence: bool = False
    required_evidence_categories: tuple[str, ...] = ()
    requirements: list[StructuredRequirementEvidence] = field(default_factory=list)
    trace_links: list[StructuredTraceLinkEvidence] = field(default_factory=list)


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
    requirement_ids: set[UUID],
    trace_link_ids: set[UUID],
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
        ) or (
            source.source_type == EvidenceSourceType.REQUIREMENT and source.record_id in requirement_ids
        ) or (
            source.source_type == EvidenceSourceType.TRACEABILITY and source.record_id in trace_link_ids
        )
        if include:
            retained.append(source)
    return retained


def _category_coverage(*, selected: bool, available: int, included: int) -> EvidenceCategoryCoverage:
    omitted = available - included
    return EvidenceCategoryCoverage(
        selected=selected,
        available=available,
        included=included,
        omitted=omitted,
        complete=(omitted == 0) if selected else None,
    )


def _coverage_warning(category: str, coverage: EvidenceCategoryCoverage) -> str | None:
    return _coverage_warning_for_bound(category, coverage, bound_label="configured limits")


def _coverage_warning_for_bound(
    category: str,
    coverage: EvidenceCategoryCoverage,
    *,
    bound_label: str,
) -> str | None:
    label = category.replace("_", " ")
    if not coverage.selected:
        return (
            f"Aggregate or absence claims about {label} cannot be supported because "
            f"{label} evidence was not selected."
        )
    if category == "documents":
        return (
            "Aggregate or absence claims about documents are limited because semantic "
            "retrieval is top-k evidence, not a complete document corpus."
        )
    if coverage.complete:
        return None
    record_label = {
        "issues": "issue",
        "tests": "test",
        "deployments": "deployment",
        "comments": "comment",
        "requirements": "requirement",
        "trace_links": "verified trace link",
    }.get(category, label)
    return (
        f"Aggregate or absence claims about {label} are limited because "
        f"{coverage.omitted} of {coverage.available} {record_label} records were omitted by {bound_label}."
    )


INPUT_BUDGET_TRUNCATION_WARNING = (
    "Evidence context was additionally truncated to fit the grounded-analysis input budget"
)


def rebuild_bounded_evidence_context(
    context: BoundedEvidenceContext,
    *,
    issues: list[StructuredIssueEvidence],
    tests: list[StructuredTestEvidence],
    deployments: list[StructuredDeploymentEvidence],
    comments: list[StructuredCommentEvidence],
    documents: list[DocumentEvidenceItem],
    requirements: list[StructuredRequirementEvidence],
    trace_links: list[StructuredTraceLinkEvidence],
    input_budget_truncated: bool = False,
) -> BoundedEvidenceContext:
    """Return an immutable-equivalent bounded view with identity-matched sources.

    The source identifiers were assigned before count bounding.  This helper
    deliberately filters those original labels rather than generating labels
    from the retained list, so later citation validation sees only evidence
    actually supplied to the LLM without renumbering it.
    """
    requirements = list(requirements)
    trace_links = [
        item for item in trace_links if item.requirement_id in {requirement.id for requirement in requirements}
    ]
    retained_sources = _filter_sources(
        context.sources,
        issue_ids={item.id for item in issues},
        test_ids={item.id for item in tests},
        deployment_ids={item.id for item in deployments},
        comment_ids={item.id for item in comments},
        chunk_ids={item.chunk_id for item in documents},
        requirement_ids={item.id for item in requirements},
        trace_link_ids={item.id for item in trace_links},
    )
    stats = EvidenceContextStats(
        available_issues=context.stats.available_issues,
        included_issues=len(issues),
        omitted_issues=context.stats.available_issues - len(issues),
        available_tests=context.stats.available_tests,
        included_tests=len(tests),
        omitted_tests=context.stats.available_tests - len(tests),
        available_deployments=context.stats.available_deployments,
        included_deployments=len(deployments),
        omitted_deployments=context.stats.available_deployments - len(deployments),
        available_comments=context.stats.available_comments,
        included_comments=len(comments),
        omitted_comments=context.stats.available_comments - len(comments),
        available_documents=context.stats.available_documents,
        included_documents=len(documents),
        omitted_documents=context.stats.available_documents - len(documents),
        available_requirements=context.stats.available_requirements,
        included_requirements=len(requirements),
        omitted_requirements=context.stats.available_requirements - len(requirements),
        available_trace_links=context.stats.available_trace_links,
        included_trace_links=len(trace_links),
        omitted_trace_links=context.stats.available_trace_links - len(trace_links),
        available_sources=context.stats.available_sources,
        included_sources=len(retained_sources),
        truncated=context.stats.truncated or input_budget_truncated,
    )
    coverage = EvidenceCoverage(
        selected_scope=context.coverage.selected_scope,
        issues=_category_coverage(
            selected=context.coverage.issues.selected,
            available=stats.available_issues,
            included=stats.included_issues,
        ),
        tests=_category_coverage(
            selected=context.coverage.tests.selected,
            available=stats.available_tests,
            included=stats.included_tests,
        ),
        deployments=_category_coverage(
            selected=context.coverage.deployments.selected,
            available=stats.available_deployments,
            included=stats.included_deployments,
        ),
        comments=_category_coverage(
            selected=context.coverage.comments.selected,
            available=stats.available_comments,
            included=stats.included_comments,
        ),
        documents=_category_coverage(
            selected=context.coverage.documents.selected,
            available=stats.available_documents,
            included=stats.included_documents,
        ),
        requirements=_category_coverage(
            selected=context.coverage.requirements.selected,
            available=stats.available_requirements,
            included=stats.included_requirements,
        ),
        trace_links=_category_coverage(
            selected=context.coverage.trace_links.selected,
            available=stats.available_trace_links,
            included=stats.included_trace_links,
        ),
    )
    warnings = list(context.warnings)
    if input_budget_truncated:
        warnings.append(INPUT_BUDGET_TRUNCATION_WARNING)
        if not context.multi_sprint_comparison and context.requires_complete_evidence:
            for category in context.required_evidence_categories:
                for bound_label in ("configured limits", "the grounded-analysis input budget"):
                    old_warning = _coverage_warning_for_bound(
                        category,
                        getattr(context.coverage, category),
                        bound_label=bound_label,
                    )
                    if old_warning in warnings:
                        warnings.remove(old_warning)
                warning = _coverage_warning_for_bound(
                    category,
                    getattr(coverage, category),
                    bound_label="the grounded-analysis input budget",
                )
                if warning is not None:
                    warnings.append(warning)
    return BoundedEvidenceContext(
        query=context.query,
        project_key=context.project_key,
        intent=context.intent,
        employee_reference=context.employee_reference,
        sprint_reference=context.sprint_reference,
        issues=list(issues),
        tests=list(tests),
        deployments=list(deployments),
        comments=list(comments),
        documents=list(documents),
        requirements=requirements,
        trace_links=trace_links,
        sources=retained_sources,
        stats=stats,
        warnings=_deduplicate_warnings(warnings),
        coverage=coverage,
        sprint_references=context.sprint_references,
        multi_sprint_comparison=context.multi_sprint_comparison,
        requires_complete_evidence=context.requires_complete_evidence,
        required_evidence_categories=context.required_evidence_categories,
    )


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
    available_requirements = list(getattr(structured, "requirements", [])) if structured is not None else []
    available_trace_links = list(getattr(structured, "trace_links", [])) if structured is not None else []

    issues = available_issues[: effective_limits.max_issues]
    tests = available_tests[: effective_limits.max_tests]
    deployments = available_deployments[: effective_limits.max_deployments]
    comments = available_comments[: effective_limits.max_comments]
    documents = available_documents[: effective_limits.max_documents]
    requirements = available_requirements[: effective_limits.max_requirements]
    retained_requirement_ids = {item.id for item in requirements}
    trace_links = [
        item for item in available_trace_links if item.requirement_id in retained_requirement_ids
    ][: effective_limits.max_trace_links]
    sources = _filter_sources(
        cited_evidence.sources,
        issue_ids={item.id for item in issues},
        test_ids={item.id for item in tests},
        deployment_ids={item.id for item in deployments},
        comment_ids={item.id for item in comments},
        chunk_ids={item.chunk_id for item in documents},
        requirement_ids=retained_requirement_ids,
        trace_link_ids={item.id for item in trace_links},
    )

    counts = (
        len(available_issues), len(issues), len(available_tests), len(tests),
        len(available_deployments), len(deployments), len(available_comments), len(comments),
        len(available_documents), len(documents),
        len(available_requirements), len(requirements),
        len(available_trace_links), len(trace_links),
    )
    truncated = any(available > included for available, included in zip(counts[::2], counts[1::2]))
    coverage = EvidenceCoverage(
        selected_scope=(
            getattr(structured, "issue_scope", "PROJECT")
            if structured is not None
            else "DOCUMENT_RETRIEVAL" if document is not None else "NO_EVIDENCE"
        ),
        issues=_category_coverage(
            selected=structured is not None,
            available=len(available_issues),
            included=len(issues),
        ),
        tests=_category_coverage(
            selected=structured is not None,
            available=len(available_tests),
            included=len(tests),
        ),
        deployments=_category_coverage(
            selected=structured is not None,
            available=len(available_deployments),
            included=len(deployments),
        ),
        comments=_category_coverage(
            selected=structured is not None,
            available=len(available_comments),
            included=len(comments),
        ),
        documents=_category_coverage(
            selected=document is not None,
            available=len(available_documents),
            included=len(documents),
        ),
        requirements=_category_coverage(
            selected=structured is not None and getattr(hybrid, "needs_verified_traceability_evidence", False),
            available=len(available_requirements),
            included=len(requirements),
        ),
        trace_links=_category_coverage(
            selected=structured is not None and getattr(hybrid, "needs_verified_traceability_evidence", False),
            available=len(available_trace_links),
            included=len(trace_links),
        ),
    )
    warnings = list(hybrid.warnings)
    if truncated:
        warnings.append("Evidence context was truncated by configured limits")
    if not getattr(hybrid, "multi_sprint_comparison", False) and getattr(
        hybrid, "requires_complete_evidence", False
    ):
        for category in getattr(hybrid, "required_evidence_categories", ()):
            warning = _coverage_warning(category, getattr(coverage, category))
            if warning is not None:
                warnings.append(warning)
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
        requirements=requirements,
        trace_links=trace_links,
        sources=sources,
        stats=EvidenceContextStats(
            available_issues=len(available_issues), included_issues=len(issues), omitted_issues=len(available_issues) - len(issues),
            available_tests=len(available_tests), included_tests=len(tests), omitted_tests=len(available_tests) - len(tests),
            available_deployments=len(available_deployments), included_deployments=len(deployments), omitted_deployments=len(available_deployments) - len(deployments),
            available_comments=len(available_comments), included_comments=len(comments), omitted_comments=len(available_comments) - len(comments),
            available_documents=len(available_documents), included_documents=len(documents), omitted_documents=len(available_documents) - len(documents),
            available_requirements=len(available_requirements), included_requirements=len(requirements), omitted_requirements=len(available_requirements) - len(requirements),
            available_trace_links=len(available_trace_links), included_trace_links=len(trace_links), omitted_trace_links=len(available_trace_links) - len(trace_links),
            available_sources=len(cited_evidence.sources), included_sources=len(sources), truncated=truncated,
        ),
        warnings=_deduplicate_warnings(warnings),
        coverage=coverage,
        sprint_references=tuple(getattr(hybrid, "sprint_references", ())),
        multi_sprint_comparison=getattr(hybrid, "multi_sprint_comparison", False),
        requires_complete_evidence=getattr(hybrid, "requires_complete_evidence", False),
        required_evidence_categories=tuple(
            getattr(hybrid, "required_evidence_categories", ())
        ),
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
