"""Project-scoped endpoint for deterministic hybrid evidence orchestration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.document_evidence import _response_from_package as document_evidence_response
from app.routers.structured_evidence import _response_from_package as structured_evidence_response
from app.schemas.hybrid_evidence import HybridEvidenceRequest, HybridEvidenceResponse
from app.services.hybrid_evidence_service import (
    HybridEvidenceError,
    HybridEvidencePackage,
    build_hybrid_evidence,
)


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def _response_from_package(package: HybridEvidencePackage) -> HybridEvidenceResponse:
    return HybridEvidenceResponse(
        query=package.query,
        project_key=package.project_key,
        intent=package.intent,
        needs_structured_evidence=package.needs_structured_evidence,
        needs_document_evidence=package.needs_document_evidence,
        employee_reference=package.employee_reference,
        sprint_reference=package.sprint_reference,
        requested_document_types=package.requested_document_types,
        structured_evidence=(
            structured_evidence_response(package.structured_evidence)
            if package.structured_evidence is not None
            else None
        ),
        document_evidence=(
            document_evidence_response(package.document_evidence)
            if package.document_evidence is not None
            else None
        ),
        warnings=package.warnings,
    )


@router.post(
    "/{project_key}/intelligence/evidence",
    response_model=HybridEvidenceResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid evidence request or scope"},
    },
)
def get_hybrid_evidence(
    project_key: str,
    request: HybridEvidenceRequest,
    db: Session = Depends(get_db),
) -> HybridEvidenceResponse:
    """Orchestrate evidence packages only; no answer, citation, or retrieval logic lives here."""
    try:
        package = build_hybrid_evidence(db, project_key, request.query, top_k=request.top_k)
    except HybridEvidenceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_package(package)
