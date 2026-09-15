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


router = APIRouter(prefix="/projects", tags=["Intelligence"])


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
        limits = (
            EvidenceContextLimits(**request.limits.model_dump(exclude_none=True))
            if request.limits is not None
            else None
        )
        context = build_evidence_context(
            db, project_key, request.query, top_k=request.top_k, limits=limits
        )
    except EvidenceContextError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_context(context)
