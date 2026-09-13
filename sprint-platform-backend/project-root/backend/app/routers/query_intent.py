"""Project-scoped query-intent classification endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas.query_intent import QueryIntentRequest, QueryIntentResponse
from app.services.query_intent_service import QueryIntentError, classify_query_intent


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(select(Project).where(Project.project_key == project_key))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_key}/intelligence/classify",
    response_model=QueryIntentResponse,
    responses={404: {"description": "Project not found"}},
)
def classify_project_query(
    project_key: str,
    request: QueryIntentRequest,
    db: Session = Depends(get_db),
) -> QueryIntentResponse:
    """Return deterministic routing hints only; this endpoint retrieves no evidence."""
    _get_project(db, project_key)
    try:
        result = classify_query_intent(request.query)
    except QueryIntentError as error:
        raise HTTPException(status_code=422, detail=error.args[0]) from error

    return QueryIntentResponse(
        query=result.query,
        intent=result.intent,
        needs_structured_evidence=result.needs_structured_evidence,
        needs_document_evidence=result.needs_document_evidence,
        employee_reference=result.employee_reference,
        sprint_reference=result.sprint_reference,
        document_types=result.document_types,
        matched_signals=result.matched_signals,
    )
