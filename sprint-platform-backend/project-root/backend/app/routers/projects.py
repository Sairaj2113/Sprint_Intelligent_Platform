from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.database import get_db
from app.models import Employee, Project, ProjectMember, Sprint
from app.schemas.project import ProjectMemberResponse, ProjectResponse
from app.schemas.sprint import SprintResponse

router = APIRouter(prefix="/projects", tags=["Projects"])


def _get_project(db: Session, project_key: str) -> Project:
    project = db.scalar(
        select(Project)
        .options(joinedload(Project.project_lead))
        .where(Project.project_key == project_key)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    statement = select(Project).options(joinedload(Project.project_lead)).order_by(Project.project_key)
    return list(db.scalars(statement))


@router.get("/{project_key}/members", response_model=list[ProjectMemberResponse])
def list_project_members(
    project_key: str, db: Session = Depends(get_db)
) -> list[ProjectMember]:
    project = _get_project(db, project_key)
    statement = (
        select(ProjectMember)
        .join(ProjectMember.employee)
        .options(selectinload(ProjectMember.employee))
        .where(ProjectMember.project_id == project.id)
        .order_by(Employee.employee_code)
    )
    return list(db.scalars(statement))


@router.get("/{project_key}/sprints", response_model=list[SprintResponse])
def list_project_sprints(
    project_key: str, db: Session = Depends(get_db)
) -> list[Sprint]:
    project = _get_project(db, project_key)
    statement = select(Sprint).where(Sprint.project_id == project.id).order_by(Sprint.start_date)
    return list(db.scalars(statement))


@router.get("/{project_key}", response_model=ProjectResponse)
def get_project(project_key: str, db: Session = Depends(get_db)) -> Project:
    return _get_project(db, project_key)
