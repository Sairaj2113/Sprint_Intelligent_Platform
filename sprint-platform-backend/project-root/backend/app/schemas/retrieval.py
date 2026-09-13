"""Request and response schemas for project-scoped semantic retrieval."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.document import DocumentType


class SemanticSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    document_types: list[DocumentType] | None = None

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank")
        return value


class SemanticSearchResult(BaseModel):
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


class SemanticSearchResponse(BaseModel):
    query: str
    result_count: int
    results: list[SemanticSearchResult]
