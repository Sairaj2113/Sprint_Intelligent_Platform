"""
Import all ORM models here so that:

1. `Base.metadata` is aware of every table (needed for Alembic
   `--autogenerate` to detect them).
2. Application code can simply do `from app.models import Employee, Issue, ...`
"""
from app.models.employee import Employee
from app.models.project import Project, ProjectMethodology
from app.models.project_member import ProjectMember
from app.models.sprint import Sprint
from app.models.issue import Issue
from app.models.issue_history import IssueHistory
from app.models.test_result import TestResult
from app.models.deployment import Deployment
from app.models.comment import Comment

__all__ = [
    "Employee",
    "Project",
    "ProjectMember",
    "ProjectMethodology",
    "Sprint",
    "Issue",
    "IssueHistory",
    "TestResult",
    "Deployment",
    "Comment",
]
