"""Project-scoped semantic document-evidence endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.document_evidence import (
    DocumentEvidenceItemRead,
    DocumentEvidenceRequest,
    DocumentEvidenceResponse,
)
from app.services.document_evidence_service import (
    DocumentEvidenceError,
    DocumentEvidencePackage,
    build_document_evidence,
)


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def _response_from_package(package: DocumentEvidencePackage) -> DocumentEvidenceResponse:
    return DocumentEvidenceResponse(
        query=package.query,
        project_id=package.project_id,
        project_key=package.project_key,
        requested_document_types=package.requested_document_types,
        top_k=package.top_k,
        result_count=package.result_count,
        results=[DocumentEvidenceItemRead(**item.__dict__) for item in package.results],
        warnings=package.warnings,
    )


@router.post(
    "/{project_key}/intelligence/document-evidence",
    response_model=DocumentEvidenceResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid document-evidence request"},
    },
)
def get_document_evidence(
    project_key: str,
    request: DocumentEvidenceRequest,
    db: Session = Depends(get_db),
) -> DocumentEvidenceResponse:
    """Return semantic retrieval facts only; no structured-evidence merge occurs here."""
    try:
        package = build_document_evidence(
            db,
            project_key,
            request.query,
            top_k=request.top_k,
            document_types=request.document_types,
        )
    except DocumentEvidenceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_package(package)
