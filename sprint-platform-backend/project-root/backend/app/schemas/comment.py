from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.employee import EmployeeNameSummary


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    employee_id: uuid.UUID
    content: str
    created_at: datetime.datetime
    employee: EmployeeNameSummary | None = None
