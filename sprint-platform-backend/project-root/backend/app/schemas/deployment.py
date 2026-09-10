from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.deployment import DeploymentStatus


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    deployment_status: DeploymentStatus
    environment: str | None
    deployment_date: datetime.datetime | None
    production_notes: str | None
    production_incidents: str | None
