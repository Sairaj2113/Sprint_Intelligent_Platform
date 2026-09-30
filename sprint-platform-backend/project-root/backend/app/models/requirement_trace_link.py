from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RequirementTraceLinkKind(str, enum.Enum):
    IMPLEMENTED_BY_ISSUE = "IMPLEMENTED_BY_ISSUE"
    VERIFIED_BY_TEST = "VERIFIED_BY_TEST"
    RELEASED_BY_DEPLOYMENT = "RELEASED_BY_DEPLOYMENT"


class RequirementTraceLink(Base):
    """One explicitly verified, non-transitive requirement-to-delivery link."""

    __tablename__ = "requirement_trace_links"
    __table_args__ = (
        CheckConstraint(
            "((issue_id IS NOT NULL)::integer + (test_result_id IS NOT NULL)::integer + "
            "(deployment_id IS NOT NULL)::integer) = 1",
            name="ck_requirement_trace_links_exactly_one_target",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), index=True, nullable=False
    )
    link_kind: Mapped[RequirementTraceLinkKind] = mapped_column(
        SAEnum(RequirementTraceLinkKind, name="requirement_trace_link_kind"), nullable=False
    )
    issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=True
    )
    test_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_results.id", ondelete="CASCADE"), nullable=True
    )
    deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deployments.id", ondelete="CASCADE"), nullable=True
    )
    verified_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    verified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="requirement_trace_links")
    requirement: Mapped["Requirement"] = relationship("Requirement", back_populates="trace_links")
    issue: Mapped["Issue | None"] = relationship("Issue", back_populates="requirement_trace_links")
    test_result: Mapped["TestResult | None"] = relationship("TestResult", back_populates="requirement_trace_links")
    deployment: Mapped["Deployment | None"] = relationship("Deployment", back_populates="requirement_trace_links")
    verified_by: Mapped["Employee"] = relationship("Employee", foreign_keys=[verified_by_id])
