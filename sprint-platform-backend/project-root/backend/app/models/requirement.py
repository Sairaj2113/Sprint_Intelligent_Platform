from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Requirement(Base):
    """A curated project requirement anchored to one canonical document chunk."""

    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint("project_id", "requirement_key", name="uq_requirements_project_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    requirement_key: Mapped[str] = mapped_column(String(100), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False
    )
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="requirements")
    source_chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="requirements")
    recorded_by: Mapped["Employee"] = relationship("Employee", foreign_keys=[recorded_by_id])
    trace_links: Mapped[list["RequirementTraceLink"]] = relationship(
        "RequirementTraceLink", back_populates="requirement", cascade="all, delete-orphan"
    )
