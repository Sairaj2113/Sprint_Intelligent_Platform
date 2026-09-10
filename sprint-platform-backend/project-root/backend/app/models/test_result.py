from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TestingStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"


class TestResult(Base):
    """QA testing outcome recorded against an Issue."""

    __tablename__ = "test_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False
    )
    testing_status: Mapped[TestingStatus] = mapped_column(
        SAEnum(TestingStatus, name="testing_status"),
        default=TestingStatus.NOT_STARTED,
        nullable=False,
    )
    test_cases_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_cases_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bugs_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reopened_count: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)
    testing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
    tested_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="test_results")
    tested_by_employee: Mapped["Employee"] = relationship("Employee", foreign_keys=[tested_by])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TestResult id={self.id} issue_id={self.issue_id} status={self.testing_status}>"
