from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.sprint import SprintStatus


class SprintSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: SprintStatus


class SprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    goal: str | None
    status: SprintStatus
    start_date: datetime.date | None
    end_date: datetime.date | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
