from __future__ import annotations

import datetime
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus, DocumentType


class DocumentRead(BaseModel):
    """Safe document representation for future read APIs."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    document_type: DocumentType
    title: str
    original_filename: str
    mime_type: str | None
    file_size_bytes: int | None
    status: DocumentStatus
    uploaded_at: datetime.datetime
    processed_at: datetime.datetime | None


class DocumentChunkRead(BaseModel):
    """Chunk metadata and content, deliberately excluding its embedding vector."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    project_id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int | None
    page_number: int | None
    section_title: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime.datetime


class DocumentProcessingResult(BaseModel):
    document_id: uuid.UUID
    project_id: uuid.UUID
    status: DocumentStatus
    chunk_count: int
    processed_at: datetime.datetime


class DocumentEmbeddingResult(BaseModel):
    """Embedding-persistence result that deliberately excludes raw vectors."""

    document_id: uuid.UUID
    project_id: uuid.UUID
    embedded_chunk_count: int
    embedding_dimension: int
