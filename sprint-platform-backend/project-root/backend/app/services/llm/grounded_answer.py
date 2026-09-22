"""Strict structural contract for a future grounded LLM answer."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


# Canonical source labels use a recognized uppercase prefix and a non-zero,
# non-leading-zero integer. Existence and evidence membership are not checked here.
SOURCE_ID_PATTERN = re.compile(r"^(?:ISSUE|TEST|DEPLOY|COMMENT|DOC)-[1-9]\d*$")


class GroundedClaim(BaseModel):
    """One nonblank statement with one or more structurally valid source labels."""

    model_config = ConfigDict(extra="forbid")

    statement: StrictStr
    source_ids: list[StrictStr] = Field(min_length=1)

    @field_validator("statement")
    @classmethod
    def statement_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("statement must not be blank")
        return value

    @field_validator("source_ids")
    @classmethod
    def source_ids_must_be_unique_and_canonical(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        for value in values:
            if not value.strip():
                raise ValueError("source_ids must not contain blank values")
            if value in seen:
                raise ValueError("source_ids must not contain duplicates")
            if SOURCE_ID_PATTERN.fullmatch(value) is None:
                raise ValueError("source_ids must use a canonical source label")
            seen.add(value)
        return values


class GroundedAnswer(BaseModel):
    """Provider-neutral answer structure; citation support is validated later."""

    model_config = ConfigDict(extra="forbid")

    answer: StrictStr
    claims: list[GroundedClaim]
    limitations: list[StrictStr]

    @field_validator("answer")
    @classmethod
    def answer_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("answer must not be blank")
        return value

    @field_validator("limitations")
    @classmethod
    def limitations_must_be_nonblank_and_unique(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        for value in values:
            if not value.strip():
                raise ValueError("limitations must not contain blank values")
            if value in seen:
                raise ValueError("limitations must not contain duplicates")
            seen.add(value)
        return values
