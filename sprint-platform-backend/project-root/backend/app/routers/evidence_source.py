"""Project-scoped endpoint exposing evidence packages with source metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.hybrid_evidence import _response_from_package as hybrid_evidence_response
from app.schemas.evidence_source import CitedEvidenceResponse, EvidenceSourceRead
from app.schemas.hybrid_evidence import HybridEvidenceRequest
from app.services.evidence_source_service import (
    CitedEvidencePackage,
    EvidenceSourceError,
    build_cited_evidence,
)


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def _response_from_package(package: CitedEvidencePackage) -> CitedEvidenceResponse:
    return CitedEvidenceResponse(
        evidence=hybrid_evidence_response(package.evidence),
        sources=[EvidenceSourceRead(**source.__dict__) for source in package.sources],
        source_count=package.source_count,
    )


@router.post(
    "/{project_key}/intelligence/cited-evidence",
    response_model=CitedEvidenceResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid cited-evidence request"},
    },
)
def get_cited_evidence(
    project_key: str,
    request: HybridEvidenceRequest,
    db: Session = Depends(get_db),
) -> CitedEvidenceResponse:
    """Return evidence plus provenance descriptors; source labels are not claims."""
    try:
        package = build_cited_evidence(db, project_key, request.query, top_k=request.top_k)
    except EvidenceSourceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_package(package)
