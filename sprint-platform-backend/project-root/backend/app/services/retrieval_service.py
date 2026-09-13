"""PostgreSQL pgvector retrieval limited to one project at a time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentType
from app.services.embedding_service import EmbeddingError, embed_query


class SemanticRetrievalError(Exception):
    """Controlled error raised when semantic retrieval cannot complete."""


@dataclass(frozen=True)
class SemanticRetrievalResult:
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


def search_project_documents(
    db: Session,
    project_id: UUID,
    query: str,
    top_k: int = 5,
    document_types: list[DocumentType] | None = None,
) -> list[SemanticRetrievalResult]:
    """Retrieve the closest embedded chunks using PostgreSQL cosine distance."""
    try:
        query_embedding = embed_query(query)
    except EmbeddingError as error:
        raise SemanticRetrievalError("Unable to generate retrieval query embedding") from error
    except Exception as error:
        raise SemanticRetrievalError("Unable to generate retrieval query embedding") from error

    distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(DocumentChunk, Document, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.project_id == project_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance.asc())
        .limit(top_k)
    )
    if document_types:
        statement = statement.where(Document.document_type.in_(document_types))

    try:
        rows = db.execute(statement).all()
    except Exception as error:
        raise SemanticRetrievalError("Unable to retrieve document chunks") from error

    try:
        return [
            SemanticRetrievalResult(
                document_id=document.id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                document_title=document.title,
                document_type=document.document_type,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                metadata_json=chunk.metadata_json,
                distance=float(row_distance),
            )
            for chunk, document, row_distance in rows
        ]
    except Exception as error:
        raise SemanticRetrievalError("Unable to retrieve document chunks") from error
