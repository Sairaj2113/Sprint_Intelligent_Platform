"""Safe API schemas for deterministic evidence-source provenance metadata."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel

from app.models import DocumentType
from app.schemas.hybrid_evidence import HybridEvidenceResponse
from app.services.evidence_source_service import EvidenceSourceType


class EvidenceSourceRead(BaseModel):
    source_id: str
    source_type: EvidenceSourceType
    project_key: str
    record_id: uuid.UUID | str | None
    title: str
    issue_key: str | None
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    chunk_index: int | None
    document_type: DocumentType | None
    page_number: int | None
    section_title: str | None
    metadata: dict[str, Any]


class CitedEvidenceResponse(BaseModel):
    evidence: HybridEvidenceResponse
    sources: list[EvidenceSourceRead]
    source_count: int
