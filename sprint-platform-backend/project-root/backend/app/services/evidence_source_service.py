"""Deterministic provenance descriptors for already retrieved evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DocumentType
from app.services.hybrid_evidence_service import (
    HybridEvidenceError,
    HybridEvidencePackage,
    build_hybrid_evidence,
)


class EvidenceSourceType(str, Enum):
    ISSUE = "ISSUE"
    TEST = "TEST"
    DEPLOYMENT = "DEPLOYMENT"
    COMMENT = "COMMENT"
    DOCUMENT = "DOCUMENT"


class EvidenceSourceError(Exception):
    """Controlled error raised while creating a cited evidence package."""

    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class EvidenceSource:
    """A source reference, not an independently generated evidence claim."""

    source_id: str
    source_type: EvidenceSourceType
    project_key: str
    record_id: UUID | str | None
    title: str
    issue_key: str | None
    document_id: UUID | None
    chunk_id: UUID | None
    chunk_index: int | None
    document_type: DocumentType | None
    page_number: int | None
    section_title: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class CitedEvidencePackage:
    evidence: HybridEvidencePackage
    sources: list[EvidenceSource]

    @property
    def source_count(self) -> int:
        return len(self.sources)


def _append_source(
    sources: list[EvidenceSource],
    seen: set[UUID | str],
    counters: dict[EvidenceSourceType, int],
    *,
    source_type: EvidenceSourceType,
    deduplication_key: UUID | str,
    project_key: str,
    record_id: UUID | str | None,
    title: str,
    issue_key: str | None = None,
    document_id: UUID | None = None,
    chunk_id: UUID | None = None,
    chunk_index: int | None = None,
    document_type: DocumentType | None = None,
    page_number: int | None = None,
    section_title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if deduplication_key in seen:
        return
    seen.add(deduplication_key)
    counters[source_type] += 1
    label = {
        EvidenceSourceType.ISSUE: "ISSUE",
        EvidenceSourceType.TEST: "TEST",
        EvidenceSourceType.DEPLOYMENT: "DEPLOY",
        EvidenceSourceType.COMMENT: "COMMENT",
        EvidenceSourceType.DOCUMENT: "DOC",
    }[source_type]
    sources.append(
        EvidenceSource(
            source_id=f"{label}-{counters[source_type]}",
            source_type=source_type,
            project_key=project_key,
            record_id=record_id,
            title=title,
            issue_key=issue_key,
            document_id=document_id,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
            document_type=document_type,
            page_number=page_number,
            section_title=section_title,
            metadata=metadata or {},
        )
    )


def build_evidence_sources(evidence: HybridEvidencePackage) -> list[EvidenceSource]:
    """Transform prebuilt evidence into stable source references without any I/O."""
    sources: list[EvidenceSource] = []
    counters = {source_type: 0 for source_type in EvidenceSourceType}
    seen_by_type: dict[EvidenceSourceType, set[UUID | str]] = {
        source_type: set() for source_type in EvidenceSourceType
    }

    if evidence.structured_evidence is not None:
        structured = evidence.structured_evidence
        issue_keys_by_id = {issue.id: issue.issue_key for issue in structured.issues}
        for issue in structured.issues:
            _append_source(
                sources, seen_by_type[EvidenceSourceType.ISSUE], counters,
                source_type=EvidenceSourceType.ISSUE, deduplication_key=issue.id,
                project_key=evidence.project_key, record_id=issue.id,
                title=f"{issue.issue_key}: {issue.title}", issue_key=issue.issue_key,
                metadata={
                    "status": issue.status,
                    "issue_type": issue.issue_type,
                    "story_points": issue.story_points,
                    "sprint_id": issue.sprint_id,
                    "sprint_name": issue.sprint_name,
                    "assignee_id": issue.assignee_id,
                    "assignee_name": issue.assignee_name,
                },
            )
        for test in structured.tests:
            issue_key = issue_keys_by_id.get(test.issue_id)
            _append_source(
                sources, seen_by_type[EvidenceSourceType.TEST], counters,
                source_type=EvidenceSourceType.TEST, deduplication_key=test.id,
                project_key=evidence.project_key, record_id=test.id,
                title=f"Test evidence for {issue_key or test.issue_id}", issue_key=issue_key,
                metadata={
                    "issue_id": test.issue_id,
                    "testing_status": test.testing_status,
                    "test_cases_total": test.test_cases_total,
                    "test_cases_passed": test.test_cases_passed,
                    "bugs_found": test.bugs_found,
                    "reopened_count": test.reopened_count,
                    "tested_by": test.tested_by,
                    "tested_by_name": test.tested_by_name,
                    "tested_at": test.tested_at,
                },
            )
        for deployment in structured.deployments:
            issue_key = issue_keys_by_id.get(deployment.issue_id)
            _append_source(
                sources, seen_by_type[EvidenceSourceType.DEPLOYMENT], counters,
                source_type=EvidenceSourceType.DEPLOYMENT, deduplication_key=deployment.id,
                project_key=evidence.project_key, record_id=deployment.id,
                title=f"Deployment evidence for {issue_key or deployment.issue_id}", issue_key=issue_key,
                metadata={
                    "issue_id": deployment.issue_id,
                    "deployment_status": deployment.deployment_status,
                    "environment": deployment.environment,
                    "deployment_date": deployment.deployment_date,
                    "production_notes": deployment.production_notes,
                    "production_incidents": deployment.production_incidents,
                },
            )
        for comment in structured.comments:
            issue_key = issue_keys_by_id.get(comment.issue_id)
            _append_source(
                sources, seen_by_type[EvidenceSourceType.COMMENT], counters,
                source_type=EvidenceSourceType.COMMENT, deduplication_key=comment.id,
                project_key=evidence.project_key, record_id=comment.id,
                title=f"Comment on {issue_key or comment.issue_id}", issue_key=issue_key,
                metadata={
                    "issue_id": comment.issue_id,
                    "employee_id": comment.employee_id,
                    "employee_name": comment.employee_name,
                    "created_at": comment.created_at,
                },
            )

    if evidence.document_evidence is not None:
        for result in evidence.document_evidence.results:
            _append_source(
                sources, seen_by_type[EvidenceSourceType.DOCUMENT], counters,
                source_type=EvidenceSourceType.DOCUMENT, deduplication_key=result.chunk_id,
                project_key=evidence.project_key, record_id=result.chunk_id,
                title=result.document_title, document_id=result.document_id,
                chunk_id=result.chunk_id, chunk_index=result.chunk_index,
                document_type=result.document_type, page_number=result.page_number,
                section_title=result.section_title,
                metadata={
                    **{
                        key: value
                        for key, value in (result.metadata_json or {}).items()
                        if key != "content"
                    },
                    "distance": result.distance,
                },
            )
    return sources


def build_cited_evidence(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int = 5,
) -> CitedEvidencePackage:
    """Build hybrid evidence once, then attach deterministic provenance references."""
    try:
        evidence = build_hybrid_evidence(db, project_key, query, top_k=top_k)
    except HybridEvidenceError as error:
        raise EvidenceSourceError(error.detail, status_code=error.status_code) from error
    except Exception as error:
        raise EvidenceSourceError("Unable to build cited evidence") from error
    return CitedEvidencePackage(evidence=evidence, sources=build_evidence_sources(evidence))


def get_source_by_id(sources: list[EvidenceSource], source_id: str) -> EvidenceSource | None:
    """Return one exact deterministic source label, if present."""
    return next((source for source in sources if source.source_id == source_id), None)
