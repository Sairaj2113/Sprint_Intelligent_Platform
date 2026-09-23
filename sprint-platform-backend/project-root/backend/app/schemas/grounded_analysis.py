"""Safe HTTP contracts for project-scoped grounded intelligence analysis."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator

from app.models import DocumentType
from app.schemas.evidence_context import EvidenceContextLimitsRequest
from app.services.evidence_source_service import EvidenceSourceType
from app.services.llm.evidence_sufficiency import EvidenceSufficiencyStatus


class GroundedAnalysisRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)
    limits: EvidenceContextLimitsRequest | None = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class GroundedClaimRead(BaseModel):
    statement: str
    source_ids: list[str]


class GroundedAnswerRead(BaseModel):
    answer: str
    claims: list[GroundedClaimRead]
    limitations: list[str]


class CitationValidationRead(BaseModel):
    valid: bool
    cited_source_ids: list[str]
    valid_source_ids: list[str]
    invalid_source_ids: list[str]


class EvidenceSufficiencyRead(BaseModel):
    status: EvidenceSufficiencyStatus
    can_proceed: bool
    reasons: list[str]
    limitations: list[str]


class LLMUsageRead(BaseModel):
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class GenerationMetadataRead(BaseModel):
    provider: str | None
    model: str | None
    fallback_used: bool | None
    usage: LLMUsageRead | None


class GroundedAnalysisSourceRead(BaseModel):
    """Allowlisted citation metadata, excluding content and arbitrary source metadata."""

    source_id: str
    source_type: EvidenceSourceType
    title: str
    issue_key: str | None
    record_id: uuid.UUID | str | None
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    chunk_index: int | None
    document_type: DocumentType | None
    page_number: int | None
    section_title: str | None


class GroundedAnalysisResponse(BaseModel):
    question: str
    answer: GroundedAnswerRead | None
    citation_validation: CitationValidationRead | None
    evidence: EvidenceSufficiencyRead
    generation: GenerationMetadataRead
    sources: list[GroundedAnalysisSourceRead]
