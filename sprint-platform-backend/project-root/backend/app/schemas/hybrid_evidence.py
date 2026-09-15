"""API schemas for merged factual evidence packages."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import DocumentType
from app.schemas.document_evidence import DocumentEvidenceResponse
from app.schemas.structured_evidence import StructuredEvidenceResponse
from app.services.query_intent_service import QueryIntent


class HybridEvidenceRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class HybridEvidenceResponse(BaseModel):
    query: str
    project_key: str
    intent: QueryIntent
    needs_structured_evidence: bool
    needs_document_evidence: bool
    employee_reference: str | None
    sprint_reference: str | None
    requested_document_types: list[DocumentType]
    structured_evidence: StructuredEvidenceResponse | None
    document_evidence: DocumentEvidenceResponse | None
    warnings: list[str]
