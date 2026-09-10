from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.issue import IssueStatus
from app.schemas.employee import EmployeeNameSummary


class IssueHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    old_status: IssueStatus | None
    new_status: IssueStatus
    changed_by: uuid.UUID | None
    changed_at: datetime.datetime
    notes: str | None
    changed_by_employee: EmployeeNameSummary | None = None
