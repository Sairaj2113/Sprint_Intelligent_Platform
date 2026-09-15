"""API schemas for bounded deterministic evidence context."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.document_evidence import DocumentEvidenceItemRead
from app.schemas.evidence_source import EvidenceSourceRead
from app.schemas.structured_evidence import (
    StructuredCommentEvidenceRead,
    StructuredDeploymentEvidenceRead,
    StructuredIssueEvidenceRead,
    StructuredTestEvidenceRead,
)
from app.services.query_intent_service import QueryIntent


class EvidenceContextLimitsRequest(BaseModel):
    max_issues: int | None = Field(default=None, ge=0, le=100)
    max_tests: int | None = Field(default=None, ge=0, le=100)
    max_deployments: int | None = Field(default=None, ge=0, le=100)
    max_comments: int | None = Field(default=None, ge=0, le=100)
    max_documents: int | None = Field(default=None, ge=0, le=20)


class EvidenceContextRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    limits: EvidenceContextLimitsRequest | None = None


class EvidenceContextStatsRead(BaseModel):
    available_issues: int
    included_issues: int
    omitted_issues: int
    available_tests: int
    included_tests: int
    omitted_tests: int
    available_deployments: int
    included_deployments: int
    omitted_deployments: int
    available_comments: int
    included_comments: int
    omitted_comments: int
    available_documents: int
    included_documents: int
    omitted_documents: int
    available_sources: int
    included_sources: int
    truncated: bool


class BoundedEvidenceContextResponse(BaseModel):
    query: str
    project_key: str
    intent: QueryIntent
    employee_reference: str | None
    sprint_reference: str | None
    issues: list[StructuredIssueEvidenceRead]
    tests: list[StructuredTestEvidenceRead]
    deployments: list[StructuredDeploymentEvidenceRead]
    comments: list[StructuredCommentEvidenceRead]
    documents: list[DocumentEvidenceItemRead]
    sources: list[EvidenceSourceRead]
    stats: EvidenceContextStatsRead
    warnings: list[str]
