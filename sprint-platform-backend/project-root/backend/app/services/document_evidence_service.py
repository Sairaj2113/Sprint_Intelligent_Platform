"""Intelligence-layer adapter for existing project-scoped semantic retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentType, Project
from app.services.query_intent_service import QueryIntentResult
from app.services.retrieval_service import SemanticRetrievalError, search_project_documents


class DocumentEvidenceError(Exception):
    """Controlled error raised while building a document-evidence package."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class DocumentEvidenceItem:
    document_id: UUID
    chunk_id: UUID
    chunk_index: int
    document_title: str
    document_type: DocumentType
    content: str
    page_number: int | None
    section_title: str | None
    metadata_json: dict[str, Any] | None
    distance: float


@dataclass(frozen=True)
class DocumentEvidencePackage:
    query: str
    project_id: UUID
    project_key: str
    requested_document_types: list[DocumentType]
    top_k: int
    result_count: int
    results: list[DocumentEvidenceItem]
    warnings: list[str]


def build_document_evidence(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int = 5,
    document_types: list[DocumentType] | None = None,
    retrieval_query: str | None = None,
) -> DocumentEvidencePackage:
    """Reuse semantic retrieval once while retaining the canonical public query."""
    if not isinstance(query, str) or not query.strip():
        raise DocumentEvidenceError("Query must not be blank")
    if retrieval_query is not None and (
        not isinstance(retrieval_query, str) or not retrieval_query.strip()
    ):
        raise DocumentEvidenceError("Retrieval query must not be blank")
    if not 1 <= top_k <= 20:
        raise DocumentEvidenceError("top_k must be between 1 and 20")

    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise DocumentEvidenceError("Project not found", status_code=404)

    requested_document_types = list(document_types or [])
    retrieval_document_types = requested_document_types or None
    effective_retrieval_query = retrieval_query if retrieval_query is not None else query
    try:
        retrieval_results = search_project_documents(
            db=db,
            project_id=project.id,
            query=effective_retrieval_query,
            top_k=top_k,
            document_types=retrieval_document_types,
        )
    except SemanticRetrievalError as error:
        raise DocumentEvidenceError("Unable to retrieve document evidence", status_code=500) from error
    except Exception as error:
        raise DocumentEvidenceError("Unable to retrieve document evidence", status_code=500) from error

    results = [
        DocumentEvidenceItem(
            document_id=result.document_id,
            chunk_id=result.chunk_id,
            chunk_index=result.chunk_index,
            document_title=result.document_title,
            document_type=result.document_type,
            content=result.content,
            page_number=result.page_number,
            section_title=result.section_title,
            metadata_json=result.metadata_json,
            distance=result.distance,
        )
        for result in retrieval_results
    ]
    warnings: list[str] = []
    if not results:
        warnings.append(
            "No document evidence matched the requested document types"
            if requested_document_types
            else "Document retrieval returned no evidence"
        )
    return DocumentEvidencePackage(
        query=query,
        project_id=project.id,
        project_key=project.project_key,
        requested_document_types=requested_document_types,
        top_k=top_k,
        result_count=len(results),
        results=results,
        warnings=warnings,
    )


def build_document_evidence_from_intent(
    db: Session,
    project_key: str,
    intent_result: QueryIntentResult,
    *,
    top_k: int = 5,
    retrieval_query: str | None = None,
) -> DocumentEvidencePackage | None:
    """Build document evidence only when the deterministic intent requires it."""
    if not intent_result.needs_document_evidence:
        return None
    arguments = {
        "top_k": top_k,
        "document_types": intent_result.document_types,
    }
    if retrieval_query is not None:
        arguments["retrieval_query"] = retrieval_query
    return build_document_evidence(db, project_key, intent_result.query, **arguments)
