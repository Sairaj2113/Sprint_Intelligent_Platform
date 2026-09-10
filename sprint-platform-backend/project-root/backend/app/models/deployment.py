from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeploymentStatus(str, enum.Enum):
    NOT_DEPLOYED = "NOT_DEPLOYED"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    FAILED = "FAILED"


class Deployment(Base):
    """A deployment event associated with an Issue."""

    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=False
    )
    deployment_status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(DeploymentStatus, name="deployment_status"),
        default=DeploymentStatus.NOT_DEPLOYED,
        nullable=False,
    )
    environment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deployment_date: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    production_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    production_incidents: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="deployments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Deployment id={self.id} issue_id={self.issue_id} status={self.deployment_status}>"
