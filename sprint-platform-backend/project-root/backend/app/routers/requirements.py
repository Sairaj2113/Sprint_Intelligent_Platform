"""Curated requirement and verified trace-link APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.requirement import (
    RequirementCreate,
    RequirementRead,
    RequirementTraceLinkCreate,
    RequirementTraceLinkRead,
)
from app.services.requirement_traceability_service import (
    RequirementTraceabilityError,
    create_requirement,
    create_verified_trace_link,
    get_requirement,
    list_requirements,
    list_trace_links,
)


router = APIRouter(prefix="/projects", tags=["Requirements"])


def _commit(db: Session, item: object) -> object:
    try:
        db.commit()
        db.refresh(item)
        return item
    except Exception as error:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to persist verified traceability") from error


@router.post("/{project_key}/requirements", response_model=RequirementRead, status_code=status.HTTP_201_CREATED)
def create_project_requirement(project_key: str, request: RequirementCreate, db: Session = Depends(get_db)) -> object:
    try:
        requirement = create_requirement(
            db, project_key, requirement_key=request.requirement_key, statement=request.statement,
            source_chunk_id=request.source_chunk_id, recorded_by_id=request.recorded_by,
        )
        return _commit(db, requirement)
    except RequirementTraceabilityError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{project_key}/requirements", response_model=list[RequirementRead])
def get_project_requirements(project_key: str, db: Session = Depends(get_db)) -> list[object]:
    try:
        return list_requirements(db, project_key)
    except RequirementTraceabilityError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{project_key}/requirements/{requirement_key}", response_model=RequirementRead)
def get_project_requirement(project_key: str, requirement_key: str, db: Session = Depends(get_db)) -> object:
    try:
        return get_requirement(db, project_key, requirement_key)
    except RequirementTraceabilityError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/{project_key}/requirements/{requirement_key}/trace-links", response_model=RequirementTraceLinkRead, status_code=status.HTTP_201_CREATED)
def create_project_trace_link(project_key: str, requirement_key: str, request: RequirementTraceLinkCreate, db: Session = Depends(get_db)) -> object:
    try:
        link = create_verified_trace_link(
            db, project_key, requirement_key, link_kind=request.link_kind, issue_id=request.issue_id,
            test_result_id=request.test_result_id, deployment_id=request.deployment_id,
            verified_by_id=request.verified_by, notes=request.notes,
        )
        return _commit(db, link)
    except RequirementTraceabilityError as error:
        db.rollback()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/{project_key}/requirements/{requirement_key}/trace-links", response_model=list[RequirementTraceLinkRead])
def get_project_trace_links(project_key: str, requirement_key: str, db: Session = Depends(get_db)) -> list[object]:
    try:
        return list_trace_links(db, project_key, requirement_key)
    except RequirementTraceabilityError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
