from __future__ import annotations

import datetime as dt
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models.deployment import DeploymentStatus
from app.models.issue import IssueStatus, IssueType
from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.services import structured_evidence_service as service
from app.services.structured_evidence_service import StructuredEvidenceError


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAIRAJ_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
ANJALI_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SPRINT_ONE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SPRINT_TWO_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
ISSUE_ONE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
ISSUE_TWO_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


def project() -> SimpleNamespace:
    return SimpleNamespace(
        id=PROJECT_ID,
        project_key="BLI",
        name="Bank Loan Intelligence",
        status=ProjectStatus.ACTIVE,
        methodology=ProjectMethodology.SCRUM,
    )


def employees() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id=SAIRAJ_ID, employee_code="EMP001", name="Sairaj Pankar", role="Engineer", department="Engineering"),
        SimpleNamespace(id=ANJALI_ID, employee_code="EMP002", name="Anjali Sharma", role="QA", department="Quality"),
    ]


def sprints() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(id=SPRINT_ONE_ID, name="Foundation", status=SprintStatus.COMPLETED, start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 14), created_at=dt.datetime(2026, 1, 1)),
        SimpleNamespace(id=SPRINT_TWO_ID, name="Assessment API", status=SprintStatus.ACTIVE, start_date=dt.date(2026, 1, 15), end_date=dt.date(2026, 1, 28), created_at=dt.datetime(2026, 1, 2)),
    ]


def issue(issue_id: uuid.UUID, *, assignee_id: uuid.UUID, sprint_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=issue_id,
        issue_key=f"BLI-{1 if issue_id == ISSUE_ONE_ID else 2}",
        title="Evidence issue",
        issue_type=IssueType.STORY,
        status=IssueStatus.DONE,
        story_points=5,
        assignee_id=assignee_id,
        sprint_id=sprint_id,
        created_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
        completed_at=dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
    )


def test_result(issue_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), issue_id=issue_id, testing_status=TestingStatus.PASSED,
        test_cases_total=10, test_cases_passed=10, bugs_found=0, reopened_count=0,
        tested_by=ANJALI_ID, tested_at=dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
    )


def deployment(issue_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), issue_id=issue_id, deployment_status=DeploymentStatus.STAGING,
        environment="staging", deployment_date=dt.datetime(2026, 1, 3, tzinfo=dt.UTC),
        production_notes=None, production_incidents=None,
    )


def comment(issue_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), issue_id=issue_id, employee_id=ANJALI_ID,
        content="QA evidence", created_at=dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
    )


class StructuredEvidenceServiceTests(unittest.TestCase):
    def _db(
        self,
        issues: list[SimpleNamespace],
        tests: list[SimpleNamespace] | None = None,
        deployments: list[SimpleNamespace] | None = None,
        comments: list[SimpleNamespace] | None = None,
        project_value: object | None = None,
        sprint_values: list[SimpleNamespace] | None = None,
        employee_values: list[SimpleNamespace] | None = None,
    ) -> Mock:
        db = Mock()
        db.scalar.return_value = None if project_value is False else (
            project() if project_value is None else project_value
        )
        db.scalars.side_effect = [
            employees() if employee_values is None else employee_values,
            sprints() if sprint_values is None else sprint_values,
            issues,
            [],
            tests or [],
            deployments or [],
            comments or [],
        ]
        return db

    def test_project_wide_evidence_uses_bulk_related_queries(self) -> None:
        first = issue(ISSUE_ONE_ID, assignee_id=SAIRAJ_ID, sprint_id=SPRINT_ONE_ID)
        second = issue(ISSUE_TWO_ID, assignee_id=ANJALI_ID, sprint_id=SPRINT_TWO_ID)
        db = self._db([first, second], [test_result(ISSUE_ONE_ID)], [deployment(ISSUE_ONE_ID)], [comment(ISSUE_ONE_ID)])

        package = service.build_structured_evidence(db, "BLI")

        self.assertEqual(package.issue_scope, "PROJECT")
        self.assertEqual(package.issue_count, 2)
        self.assertEqual(package.test_evidence_count, 1)
        self.assertEqual(package.deployment_evidence_count, 1)
        self.assertEqual(package.comment_evidence_count, 1)
        self.assertIsNone(package.employee)
        self.assertIsNone(package.sprint)
        self.assertEqual(db.scalars.call_count, 7)
        self.assertFalse(hasattr(package, "employee_rank"))
        self.assertFalse(hasattr(package, "performance_score"))

    def test_employee_references_resolve_by_first_name_full_name_and_code(self) -> None:
        selected = [issue(ISSUE_ONE_ID, assignee_id=SAIRAJ_ID, sprint_id=SPRINT_ONE_ID)]
        for reference in ("Sairaj", "Sairaj Pankar", "EMP001"):
            with self.subTest(reference=reference):
                package = service.build_structured_evidence(self._db(selected), "BLI", reference)
                self.assertEqual(package.employee.name, "Sairaj Pankar")
                self.assertTrue(package.employee_scope_active)
                self.assertEqual(package.issue_scope, "EMPLOYEE_ASSIGNED")

    def test_sprint_and_employee_sprint_scopes_restrict_issue_and_related_evidence(self) -> None:
        selected = [issue(ISSUE_ONE_ID, assignee_id=SAIRAJ_ID, sprint_id=SPRINT_TWO_ID)]
        db = self._db(selected, [test_result(ISSUE_ONE_ID)], [deployment(ISSUE_ONE_ID)], [comment(ISSUE_ONE_ID)])

        package = service.build_structured_evidence(db, "BLI", "Sairaj", "Sprint 2")

        self.assertEqual(package.sprint.name, "Assessment API")
        self.assertEqual(package.issue_scope, "EMPLOYEE_ASSIGNED_SPRINT")
        self.assertEqual([item.id for item in package.issues], [ISSUE_ONE_ID])
        self.assertEqual([item.issue_id for item in package.tests], [ISSUE_ONE_ID])
        self.assertEqual([item.issue_id for item in package.deployments], [ISSUE_ONE_ID])
        self.assertEqual([item.issue_id for item in package.comments], [ISSUE_ONE_ID])
        issue_statement = db.scalars.call_args_list[2].args[0]
        self.assertIn("issues.sprint_id", str(issue_statement))
        self.assertIn("issues.assignee_id", str(issue_statement))

    def test_missing_ambiguous_and_cross_project_scopes_are_rejected(self) -> None:
        with self.assertRaises(StructuredEvidenceError):
            service.build_structured_evidence(self._db([]), "BLI", "Missing")

        ambiguous_employees = employees() + [
            SimpleNamespace(id=uuid.uuid4(), employee_code="EMP003", name="Sairaj Other", role=None, department=None)
        ]
        with self.assertRaises(StructuredEvidenceError) as ambiguous:
            service.build_structured_evidence(self._db([], employee_values=ambiguous_employees), "BLI", "Sairaj")
        self.assertIn("ambiguous", ambiguous.exception.detail)

        with self.assertRaises(StructuredEvidenceError):
            service.build_structured_evidence(self._db([]), "BLI", sprint_reference="Sprint 3")

        cross_project_sprints = [
            SimpleNamespace(id=uuid.uuid4(), name="Other project sprint", status=SprintStatus.ACTIVE, start_date=dt.date(2026, 1, 1), end_date=None, created_at=dt.datetime(2026, 1, 1))
        ]
        with self.assertRaises(StructuredEvidenceError):
            service.build_structured_evidence(self._db([], sprint_values=cross_project_sprints), "BLI", sprint_reference="Sprint 2")

    def test_missing_project_and_empty_evidence_are_safe(self) -> None:
        missing_db = self._db([], project_value=False)
        with self.assertRaises(StructuredEvidenceError) as missing:
            service.build_structured_evidence(missing_db, "MISSING")
        self.assertEqual(missing.exception.status_code, 404)

        package = service.build_structured_evidence(self._db([]), "BLI", "Sairaj", "Sprint 2")
        self.assertEqual(package.issues, [])
        self.assertIn("Employee has no assigned issues in the selected scope", package.warnings)
        self.assertIn("Sprint contains no issues in the selected scope", package.warnings)
        self.assertIn("Selected issue scope has no tests", package.warnings)
        self.assertIn("Selected issue scope has no deployments", package.warnings)

    def test_existing_contribution_workflow_and_kpi_services_are_reused(self) -> None:
        selected = [issue(ISSUE_ONE_ID, assignee_id=SAIRAJ_ID, sprint_id=SPRINT_ONE_ID)]
        db = self._db(selected)
        with patch.object(service, "build_employee_contribution_evidence", return_value=Mock()) as contribution, patch.object(
            service, "build_workflow_evidence", return_value=Mock()
        ) as workflow, patch.object(service, "calculate_issue_metrics", return_value=Mock()) as issue_metrics:
            package = service.build_structured_evidence(db, "BLI", "Sairaj")

        contribution.assert_called_once()
        workflow.assert_called_once()
        issue_metrics.assert_called_once()
        self.assertIsNotNone(package.contribution)
        self.assertIsNotNone(package.workflow)
        self.assertIs(package.kpis.issue_metrics, issue_metrics.return_value)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
