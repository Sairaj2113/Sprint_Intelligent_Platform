from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.test_result import TestingStatus
from app.schemas.employee import EmployeeNameSummary


class TestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    testing_status: TestingStatus
    test_cases_total: int | None
    test_cases_passed: int | None
    bugs_found: int | None
    reopened_count: int | None
    testing_notes: str | None
    tested_by: uuid.UUID | None
    tested_at: datetime.datetime | None
    tested_by_employee: EmployeeNameSummary | None = None
