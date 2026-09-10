from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.issue import IssueStatus


class IssueHistory(Base):
    """
    Append-only record of every status transition an Issue goes through.

    This table is the audit trail that a later AI / analytics step will
    use to reconstruct cycle time, time-in-status, and contribution
    signals, so status changes should always be recorded here rather than
    just overwriting Issue.status.
    """

    __tablename__ = "issue_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False
    )
    old_status: Mapped[IssueStatus | None] = mapped_column(
        SAEnum(IssueStatus, name="issue_status"), nullable=True
    )
    new_status: Mapped[IssueStatus] = mapped_column(
        SAEnum(IssueStatus, name="issue_status"), nullable=False
    )
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
    changed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="history")
    changed_by_employee: Mapped["Employee"] = relationship("Employee", foreign_keys=[changed_by])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IssueHistory id={self.id} issue_id={self.issue_id} "
            f"{self.old_status} -> {self.new_status}>"
        )
