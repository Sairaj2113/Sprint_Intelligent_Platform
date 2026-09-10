"""Development seed data for the Sprint Intelligence Platform.

Run with ``python -m app.seed`` from the backend directory, or through the
backend Docker Compose service. This module intentionally does not run during
application startup.
"""

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models import (
    Comment,
    Deployment,
    Employee,
    Issue,
    IssueHistory,
    Project,
    ProjectMember,
    Sprint,
    TestResult,
)
from app.models.issue import IssuePriority, IssueStatus, IssueType
from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus


def clear_seed_data() -> None:
    """Clear application data in foreign-key-safe order for local development.

    The Alembic version table is managed by Alembic and is intentionally not
    included here.
    """
    session = SessionLocal()
    try:
        print("Clearing development seed data...")

        # Remove tables that reference issues or employees before their parents.
        session.execute(delete(Comment))
        session.execute(delete(Deployment))
        session.execute(delete(IssueHistory))
        session.execute(delete(TestResult))
        session.execute(delete(Issue))

        # Memberships reference both projects and employees.
        session.execute(delete(ProjectMember))
        session.execute(delete(Sprint))
        session.execute(delete(Project))
        session.execute(delete(Employee))

        session.commit()
        print("Development seed data cleared")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_database() -> None:
    """Create or update the small, repeatable development verification dataset."""
    session = SessionLocal()
    try:
        print("Starting database seed...")

        employee = session.scalar(
            select(Employee).where(Employee.employee_code == "EMP001")
        )
        if employee is None:
            employee = Employee(
                employee_code="EMP001",
                name="Sairaj Pankar",
                email="sairajpankar@gmail.com",
                role="Software Engineer",
                department="Engineering",
                is_active=True,
            )
            session.add(employee)
            print("Employee created")
        else:
            employee.name = "Sairaj Pankar"
            employee.email = "sairajpankar@gmail.com"
            employee.role = "Software Engineer"
            employee.department = "Engineering"
            employee.is_active = True
            print("Employee already exists; reused")
        session.flush()

        project = session.scalar(
            select(Project).where(Project.project_key == "DEMO")
        )
        if project is None:
            project = Project(
                project_key="DEMO",
                name="Sprint Intelligence Demo",
                methodology=ProjectMethodology.SCRUM,
                status=ProjectStatus.ACTIVE,
                project_lead_id=employee.id,
            )
            session.add(project)
            print("Project created")
        else:
            project.name = "Sprint Intelligence Demo"
            project.methodology = ProjectMethodology.SCRUM
            project.status = ProjectStatus.ACTIVE
            project.project_lead_id = employee.id
            print("Project already exists; reused")
        session.flush()

        membership = session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.employee_id == employee.id,
            )
        )
        if membership is None:
            session.add(ProjectMember(project_id=project.id, employee_id=employee.id))
            print("Project membership created")
        else:
            print("Project membership already exists; reused")

        sprint = session.scalar(
            select(Sprint).where(
                Sprint.project_id == project.id,
                Sprint.name == "Sprint 1",
            )
        )
        if sprint is None:
            sprint = Sprint(
                project_id=project.id,
                name="Sprint 1",
                status=SprintStatus.PLANNED,
            )
            session.add(sprint)
            print("Sprint created")
        else:
            sprint.status = SprintStatus.PLANNED
            print("Sprint already exists; reused")
        session.flush()

        issue = session.scalar(select(Issue).where(Issue.issue_key == "DEMO-1"))
        if issue is None:
            issue = Issue(
                issue_key="DEMO-1",
                project_id=project.id,
                sprint_id=sprint.id,
                assignee_id=employee.id,
                reporter_id=employee.id,
                issue_type=IssueType.TASK,
                title="Initial platform setup",
                priority=IssuePriority.MEDIUM,
                status=IssueStatus.TODO,
                story_points=3,
            )
            session.add(issue)
            print("Issue created")
        else:
            issue.project_id = project.id
            issue.sprint_id = sprint.id
            issue.assignee_id = employee.id
            issue.reporter_id = employee.id
            issue.issue_type = IssueType.TASK
            issue.title = "Initial platform setup"
            issue.priority = IssuePriority.MEDIUM
            issue.status = IssueStatus.TODO
            issue.story_points = 3
            print("Issue already exists; reused")

        session.commit()
        print("Database seed completed successfully")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
