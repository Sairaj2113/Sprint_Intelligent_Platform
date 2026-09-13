"""API schemas for deterministic intelligence-query classification."""

from __future__ import annotations

from pydantic import BaseModel

from app.models import DocumentType
from app.services.query_intent_service import QueryIntent


class QueryIntentRequest(BaseModel):
    query: str


class QueryIntentResponse(BaseModel):
    query: str
    intent: QueryIntent
    needs_structured_evidence: bool
    needs_document_evidence: bool
    employee_reference: str | None
    sprint_reference: str | None
    document_types: list[DocumentType]
    matched_signals: list[str]
