from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IssueType(str, enum.Enum):
    EPIC = "EPIC"
    STORY = "STORY"
    TASK = "TASK"
    BUG = "BUG"
    SUBTASK = "SUBTASK"


class IssueStatus(str, enum.Enum):
    BACKLOG = "BACKLOG"
    SELECTED_FOR_SPRINT = "SELECTED_FOR_SPRINT"
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    CODE_REVIEW = "CODE_REVIEW"
    TESTING = "TESTING"
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    DONE = "DONE"


class IssuePriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Issue(Base):
    """
    The core unit of work: epic, story, task, bug or subtask.

    Status transitions are expected to be recorded in IssueHistory rather
    than simply overwritten, so that the analytics/AI layer built in a
    later step has a full audit trail to work from.
    """

    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    sprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sprints.id"), nullable=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
    parent_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id"), nullable=True
    )

    issue_type: Mapped[IssueType] = mapped_column(
        SAEnum(IssueType, name="issue_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[IssuePriority] = mapped_column(
        SAEnum(IssuePriority, name="issue_priority"),
        default=IssuePriority.MEDIUM,
        nullable=False,
    )
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        SAEnum(IssueStatus, name="issue_status"),
        default=IssueStatus.BACKLOG,
        nullable=False,
    )
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocker_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependency_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    start_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="issues")
    sprint: Mapped["Sprint"] = relationship("Sprint", back_populates="issues")
    assignee: Mapped["Employee"] = relationship(
        "Employee", back_populates="assigned_issues", foreign_keys=[assignee_id]
    )
    reporter: Mapped["Employee"] = relationship(
        "Employee", back_populates="reported_issues", foreign_keys=[reporter_id]
    )
    parent_issue: Mapped["Issue"] = relationship(
        "Issue", remote_side=[id], back_populates="subtasks"
    )
    subtasks: Mapped[list["Issue"]] = relationship("Issue", back_populates="parent_issue")

    history: Mapped[list["IssueHistory"]] = relationship(
        "IssueHistory", back_populates="issue", cascade="all, delete-orphan"
    )
    test_results: Mapped[list["TestResult"]] = relationship(
        "TestResult", back_populates="issue", cascade="all, delete-orphan"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        "Deployment", back_populates="issue", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="issue", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Issue id={self.id} key={self.issue_key} status={self.status}>"
