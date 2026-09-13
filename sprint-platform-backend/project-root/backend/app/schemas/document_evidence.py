"""API schemas for retrieved document evidence, excluding embedding vectors."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models import DocumentType


class DocumentEvidenceRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    document_types: list[DocumentType] | None = None


class DocumentEvidenceItemRead(BaseModel):
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    document_title: str
    document_type: DocumentType
    content: str
    page_number: int | None
    section_title: str | None
    metadata_json: dict[str, Any] | None
    distance: float


class DocumentEvidenceResponse(BaseModel):
    query: str
    project_id: uuid.UUID
    project_key: str
    requested_document_types: list[DocumentType]
    top_k: int
    result_count: int
    results: list[DocumentEvidenceItemRead]
    warnings: list[str]
