"""Project-scoped endpoint for bounded future-LLM evidence preparation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.document_evidence import DocumentEvidenceItemRead
from app.schemas.evidence_context import (
    BoundedEvidenceContextResponse,
    EvidenceContextRequest,
    EvidenceContextStatsRead,
)
from app.schemas.grounded_analysis import (
    CitationValidationRead,
    EvidenceSufficiencyRead,
    GenerationMetadataRead,
    GroundedAnalysisRequest,
    GroundedAnalysisResponse,
    GroundedAnalysisSourceRead,
    GroundedAnswerRead,
    LLMUsageRead,
)
from app.schemas.evidence_source import EvidenceSourceRead
from app.schemas.structured_evidence import (
    StructuredCommentEvidenceRead,
    StructuredDeploymentEvidenceRead,
    StructuredIssueEvidenceRead,
    StructuredTestEvidenceRead,
)
from app.services.evidence_context_service import (
    BoundedEvidenceContext,
    EvidenceContextError,
    EvidenceContextLimits,
    build_evidence_context,
)
from app.services.llm.base import LLMNonRetryableError, LLMRetryableError
from app.services.llm.grounded_analysis_service import (
    GroundedAnalysisError,
    GroundedAnalysisResult,
    analyze_grounded_question,
)
from app.services.llm.llm_service import LLMService


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def get_llm_service() -> LLMService:
    """Provide the Phase 10A provider-neutral service for one request."""
    return LLMService()


def _response_from_context(context: BoundedEvidenceContext) -> BoundedEvidenceContextResponse:
    return BoundedEvidenceContextResponse(
        query=context.query,
        project_key=context.project_key,
        intent=context.intent,
        employee_reference=context.employee_reference,
        sprint_reference=context.sprint_reference,
        issues=[StructuredIssueEvidenceRead(**item.__dict__) for item in context.issues],
        tests=[StructuredTestEvidenceRead(**item.__dict__) for item in context.tests],
        deployments=[StructuredDeploymentEvidenceRead(**item.__dict__) for item in context.deployments],
        comments=[StructuredCommentEvidenceRead(**item.__dict__) for item in context.comments],
        documents=[DocumentEvidenceItemRead(**item.__dict__) for item in context.documents],
        sources=[EvidenceSourceRead(**item.__dict__) for item in context.sources],
        stats=EvidenceContextStatsRead(**context.stats.__dict__),
        warnings=context.warnings,
    )


def _limits_from_request(request_limits: object | None) -> EvidenceContextLimits | None:
    return (
        EvidenceContextLimits(**request_limits.model_dump(exclude_none=True))
        if request_limits is not None
        else None
    )


def _build_context(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int,
    request_limits: object | None,
) -> BoundedEvidenceContext:
    return build_evidence_context(
        db,
        project_key,
        query,
        top_k=top_k,
        limits=_limits_from_request(request_limits),
    )


def _analysis_response(
    result: GroundedAnalysisResult,
    context: BoundedEvidenceContext,
) -> GroundedAnalysisResponse:
    return GroundedAnalysisResponse(
        question=result.question,
        answer=(GroundedAnswerRead(**result.answer.model_dump()) if result.answer is not None else None),
        citation_validation=(
            CitationValidationRead(
                valid=result.citation_validation.valid,
                cited_source_ids=list(result.citation_validation.cited_source_ids),
                valid_source_ids=list(result.citation_validation.valid_source_ids),
                invalid_source_ids=list(result.citation_validation.invalid_source_ids),
            )
            if result.citation_validation is not None
            else None
        ),
        evidence=EvidenceSufficiencyRead(
            status=result.evidence_sufficiency.status,
            can_proceed=result.evidence_sufficiency.can_proceed,
            reasons=list(result.evidence_sufficiency.reasons),
            limitations=list(result.evidence_sufficiency.limitations),
        ),
        generation=GenerationMetadataRead(
            provider=result.provider,
            model=result.model,
            fallback_used=result.fallback_used,
            usage=(LLMUsageRead(**result.usage.__dict__) if result.usage is not None else None),
        ),
        sources=[
            GroundedAnalysisSourceRead(
                source_id=source.source_id,
                source_type=source.source_type,
                title=source.title,
                issue_key=source.issue_key,
                record_id=source.record_id,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                chunk_index=source.chunk_index,
                document_type=source.document_type,
                page_number=source.page_number,
                section_title=source.section_title,
            )
            for source in context.sources
        ],
    )


@router.post(
    "/{project_key}/intelligence/context",
    response_model=BoundedEvidenceContextResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid evidence-context request"},
    },
)
def get_evidence_context(
    project_key: str,
    request: EvidenceContextRequest,
    db: Session = Depends(get_db),
) -> BoundedEvidenceContextResponse:
    """Build a bounded evidence view only; no answer or retrieval logic lives here."""
    try:
        context = _build_context(
            db,
            project_key,
            request.query,
            top_k=request.top_k,
            request_limits=request.limits,
        )
    except EvidenceContextError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_context(context)


@router.post(
    "/{project_key}/intelligence/analyze",
    response_model=GroundedAnalysisResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid analysis request"},
        502: {"description": "Unable to generate grounded analysis"},
        503: {"description": "Grounded analysis provider is temporarily unavailable"},
    },
)
def analyze_project_intelligence(
    project_key: str,
    request: GroundedAnalysisRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
) -> GroundedAnalysisResponse:
    """Build bounded evidence once, then delegate all grounded generation to Phase 10G."""
    try:
        context = _build_context(
            db,
            project_key,
            request.question,
            top_k=request.top_k,
            request_limits=request.limits,
        )
        result = analyze_grounded_question(request.question, context, llm_service)
    except EvidenceContextError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except GroundedAnalysisError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except LLMRetryableError as error:
        raise HTTPException(
            status_code=503,
            detail="Grounded analysis provider is temporarily unavailable",
        ) from error
    except LLMNonRetryableError as error:
        raise HTTPException(status_code=502, detail="Unable to generate grounded analysis") from error
    return _analysis_response(result, context)
