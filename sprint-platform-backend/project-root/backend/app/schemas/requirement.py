"""HTTP contracts for curated project requirements and verified trace links."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.requirement_trace_link import RequirementTraceLinkKind


class RequirementCreate(BaseModel):
    requirement_key: str = Field(min_length=1, max_length=100)
    statement: str = Field(min_length=1)
    source_chunk_id: uuid.UUID
    recorded_by: uuid.UUID


class RequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_key: str
    statement: str
    source_chunk_id: uuid.UUID
    recorded_by_id: uuid.UUID
    recorded_at: datetime.datetime


class RequirementTraceLinkCreate(BaseModel):
    link_kind: RequirementTraceLinkKind
    issue_id: uuid.UUID | None = None
    test_result_id: uuid.UUID | None = None
    deployment_id: uuid.UUID | None = None
    verified_by: uuid.UUID
    notes: str | None = None

    @model_validator(mode="after")
    def exactly_one_matching_target(self) -> "RequirementTraceLinkCreate":
        targets = (self.issue_id, self.test_result_id, self.deployment_id)
        if sum(value is not None for value in targets) != 1:
            raise ValueError("Exactly one trace-link target is required")
        expected = {
            RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE: self.issue_id,
            RequirementTraceLinkKind.VERIFIED_BY_TEST: self.test_result_id,
            RequirementTraceLinkKind.RELEASED_BY_DEPLOYMENT: self.deployment_id,
        }[self.link_kind]
        if expected is None:
            raise ValueError("Trace-link target does not match link_kind")
        return self


class RequirementTraceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    link_kind: RequirementTraceLinkKind
    issue_id: uuid.UUID | None
    test_result_id: uuid.UUID | None
    deployment_id: uuid.UUID | None
    verified_by_id: uuid.UUID
    verified_at: datetime.datetime
    notes: str | None
