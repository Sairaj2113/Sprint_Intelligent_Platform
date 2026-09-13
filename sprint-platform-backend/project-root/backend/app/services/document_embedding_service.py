"""Atomic persistence of generated embeddings for processed document chunks."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk, DocumentStatus
from app.services.embedding_service import EmbeddingError, embed_documents


class DocumentEmbeddingError(Exception):
    """Controlled error raised while embedding one processed document."""

    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def embed_document_chunks(db: Session, document: Document) -> int:
    """Generate and atomically persist embeddings for every chunk of a document."""
    if document.status != DocumentStatus.PROCESSED:
        raise DocumentEmbeddingError(
            "Document must be processed before embedding", status_code=409
        )

    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = list(db.scalars(statement))
    if not chunks:
        raise DocumentEmbeddingError("Document has no chunks to embed", status_code=409)

    try:
        vectors = embed_documents([chunk.content for chunk in chunks])
    except EmbeddingError as error:
        raise DocumentEmbeddingError("Unable to generate document embeddings") from error
    except Exception as error:
        raise DocumentEmbeddingError("Unable to generate document embeddings") from error

    if len(vectors) != len(chunks):
        raise DocumentEmbeddingError("Embedding result count does not match document chunks")

    try:
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        db.commit()
    except Exception as error:
        db.rollback()
        raise DocumentEmbeddingError("Unable to persist document embeddings") from error

    return len(chunks)
