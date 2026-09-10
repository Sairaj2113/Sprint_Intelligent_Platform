from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.project import ProjectMethodology, ProjectStatus
from app.schemas.employee import EmployeeResponse, EmployeeSummary


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_key: str
    name: str
    description: str | None
    methodology: ProjectMethodology | None
    status: ProjectStatus
    project_lead_id: uuid.UUID | None
    project_lead: EmployeeSummary | None = None


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    employee_id: uuid.UUID
    employee: EmployeeResponse
