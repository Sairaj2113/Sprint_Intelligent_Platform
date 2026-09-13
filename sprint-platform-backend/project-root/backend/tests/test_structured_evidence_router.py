from __future__ import annotations

import datetime as dt
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus
from app.routers import structured_evidence
from app.schemas.structured_evidence import StructuredEvidenceRequest, StructuredEvidenceResponse


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EMPLOYEE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SPRINT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def project() -> SimpleNamespace:
    return SimpleNamespace(
        id=PROJECT_ID,
        project_key="BLI",
        name="Bank Loan Intelligence",
        status=ProjectStatus.ACTIVE,
        methodology=ProjectMethodology.SCRUM,
    )


def employee() -> SimpleNamespace:
    return SimpleNamespace(
        id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj Pankar",
        role="Engineer", department="Engineering",
    )


def sprint() -> SimpleNamespace:
    return SimpleNamespace(
        id=SPRINT_ID, name="Foundation", status=SprintStatus.COMPLETED,
        start_date=dt.date(2026, 1, 1), end_date=dt.date(2026, 1, 14),
        created_at=dt.datetime(2026, 1, 1),
    )


def db_for_empty_scope() -> Mock:
    db = Mock()
    db.scalar.return_value = project()
    db.scalars.side_effect = [[employee()], [sprint()], []]
    return db


class StructuredEvidenceRouterTests(unittest.TestCase):
    def test_project_only_response_is_schema_safe_and_does_not_call_retrieval_or_embedding(self) -> None:
        db = db_for_empty_scope()
        with patch("app.services.retrieval_service.search_project_documents") as retrieval, patch(
            "app.services.embedding_service.embed_query"
        ) as embed_query:
            response = structured_evidence.get_structured_evidence(
                "BLI", StructuredEvidenceRequest(), db
            )

        self.assertIsInstance(response, StructuredEvidenceResponse)
        self.assertEqual(response.project.project_key, "BLI")
        self.assertEqual(response.issue_scope, "PROJECT")
        self.assertEqual(response.issue_count, 0)
        self.assertNotIn("embedding", StructuredEvidenceResponse.model_fields)
        retrieval.assert_not_called()
        embed_query.assert_not_called()

    def test_employee_and_sprint_request_returns_resolved_scope(self) -> None:
        db = db_for_empty_scope()
        response = structured_evidence.get_structured_evidence(
            "BLI",
            StructuredEvidenceRequest(employee_reference="Sairaj", sprint_reference="Sprint 1"),
            db,
        )

        self.assertEqual(response.employee.name, "Sairaj Pankar")
        self.assertEqual(response.sprint.name, "Foundation")
        self.assertEqual(response.issue_scope, "EMPLOYEE_ASSIGNED_SPRINT")

    def test_missing_project_unresolved_employee_and_unresolved_sprint_are_controlled(self) -> None:
        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as missing_project:
            structured_evidence.get_structured_evidence(
                "MISSING", StructuredEvidenceRequest(), missing_project_db
            )
        self.assertEqual(missing_project.exception.status_code, 404)

        missing_employee_db = db_for_empty_scope()
        missing_employee_db.scalars.side_effect = [[], [sprint()], []]
        with self.assertRaises(HTTPException) as missing_employee:
            structured_evidence.get_structured_evidence(
                "BLI", StructuredEvidenceRequest(employee_reference="Unknown"), missing_employee_db
            )
        self.assertEqual(missing_employee.exception.status_code, 422)

        missing_sprint_db = db_for_empty_scope()
        with self.assertRaises(HTTPException) as missing_sprint:
            structured_evidence.get_structured_evidence(
                "BLI", StructuredEvidenceRequest(sprint_reference="Sprint 2"), missing_sprint_db
            )
        self.assertEqual(missing_sprint.exception.status_code, 422)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
