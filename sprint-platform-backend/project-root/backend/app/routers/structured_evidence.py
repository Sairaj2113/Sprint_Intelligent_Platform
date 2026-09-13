"""Project-scoped factual structured-evidence endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.structured_evidence import (
    StructuredCommentEvidenceRead,
    StructuredDeploymentEvidenceRead,
    StructuredEmployeeEvidenceRead,
    StructuredEvidenceRequest,
    StructuredEvidenceResponse,
    StructuredIssueEvidenceRead,
    StructuredKpiEvidenceRead,
    StructuredProjectEvidenceRead,
    StructuredSprintEvidenceRead,
    StructuredTestEvidenceRead,
)
from app.services.structured_evidence_service import (
    StructuredEvidenceError,
    StructuredEvidencePackage,
    build_structured_evidence,
)


router = APIRouter(prefix="/projects", tags=["Intelligence"])


def _response_from_package(package: StructuredEvidencePackage) -> StructuredEvidenceResponse:
    return StructuredEvidenceResponse(
        project=StructuredProjectEvidenceRead(**package.project.__dict__),
        employee=(
            StructuredEmployeeEvidenceRead(**package.employee.__dict__)
            if package.employee is not None
            else None
        ),
        sprint=(
            StructuredSprintEvidenceRead(**package.sprint.__dict__)
            if package.sprint is not None
            else None
        ),
        employee_scope_active=package.employee_scope_active,
        sprint_scope_active=package.sprint_scope_active,
        issue_scope=package.issue_scope,
        issue_count=package.issue_count,
        test_evidence_count=package.test_evidence_count,
        deployment_evidence_count=package.deployment_evidence_count,
        comment_evidence_count=package.comment_evidence_count,
        issues=[StructuredIssueEvidenceRead(**item.__dict__) for item in package.issues],
        tests=[StructuredTestEvidenceRead(**item.__dict__) for item in package.tests],
        deployments=[
            StructuredDeploymentEvidenceRead(**item.__dict__) for item in package.deployments
        ],
        comments=[StructuredCommentEvidenceRead(**item.__dict__) for item in package.comments],
        contribution=package.contribution,
        workflow=package.workflow,
        kpis=StructuredKpiEvidenceRead(**package.kpis.__dict__),
        warnings=package.warnings,
    )


@router.post(
    "/{project_key}/intelligence/structured-evidence",
    response_model=StructuredEvidenceResponse,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Employee or sprint scope could not be resolved"},
    },
)
def get_structured_evidence(
    project_key: str,
    request: StructuredEvidenceRequest,
    db: Session = Depends(get_db),
) -> StructuredEvidenceResponse:
    """Return project-scoped database facts and deterministic service outputs only."""
    try:
        package = build_structured_evidence(
            db,
            project_key,
            employee_reference=request.employee_reference,
            sprint_reference=request.sprint_reference,
        )
    except StructuredEvidenceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return _response_from_package(package)
