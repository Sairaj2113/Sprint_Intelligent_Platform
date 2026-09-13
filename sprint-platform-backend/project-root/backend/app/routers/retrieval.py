"""Project-scoped semantic retrieval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas.retrieval import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
)
from app.services.retrieval_service import (
    SemanticRetrievalError,
    search_project_documents,
)


router = APIRouter(prefix="/projects", tags=["Retrieval"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_key}/retrieval/search",
    response_model=SemanticSearchResponse,
    responses={404: {"description": "Project not found"}},
)
def search_project_documents_endpoint(
    project_key: str,
    request: SemanticSearchRequest,
    db: Session = Depends(get_db),
) -> SemanticSearchResponse:
    """Return closest embedded document chunks for one project only."""
    project = _get_project(db, project_key)
    try:
        matches = search_project_documents(
            db=db,
            project_id=project.id,
            query=request.query,
            top_k=request.top_k,
            document_types=request.document_types,
        )
    except SemanticRetrievalError as error:
        raise HTTPException(status_code=500, detail="Unable to retrieve document chunks") from error

    return SemanticSearchResponse(
        query=request.query,
        result_count=len(matches),
        results=[
            SemanticSearchResult(
                document_id=match.document_id,
                chunk_id=match.chunk_id,
                chunk_index=match.chunk_index,
                document_title=match.document_title,
                document_type=match.document_type,
                content=match.content,
                page_number=match.page_number,
                section_title=match.section_title,
                metadata_json=match.metadata_json,
                distance=match.distance,
            )
            for match in matches
        ],
    )
