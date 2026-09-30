from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.routers.employee_performance import (
    get_project_employee_performance,
    get_sprint_employee_performance,
)


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
EMPLOYEE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
SPRINT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="BLI", name="Bank Loan")


def employee() -> SimpleNamespace:
    return SimpleNamespace(id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj")


def sprint() -> SimpleNamespace:
    return SimpleNamespace(id=SPRINT_ID, project_id=PROJECT_ID, name="Sprint One")


class EmployeePerformanceRouterTests(unittest.TestCase):
    def test_project_report_validates_project_employee_and_membership_before_building(self) -> None:
        db = Mock()
        db.scalar.side_effect = [project(), employee(), uuid.uuid4()]
        expected = object()
        with patch("app.routers.employee_performance._build_report", return_value=expected) as build:
            result = get_project_employee_performance("BLI", EMPLOYEE_ID, db)

        self.assertIs(result, expected)
        build.assert_called_once_with(db, project(), employee())

    def test_project_report_rejects_missing_project_employee_and_non_member(self) -> None:
        missing_project = Mock()
        missing_project.scalar.return_value = None
        with self.assertRaises(HTTPException) as project_error:
            get_project_employee_performance("MISSING", EMPLOYEE_ID, missing_project)
        self.assertEqual(project_error.exception.detail, "Project not found")

        missing_employee = Mock()
        missing_employee.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as employee_error:
            get_project_employee_performance("BLI", EMPLOYEE_ID, missing_employee)
        self.assertEqual(employee_error.exception.detail, "Employee not found")

        non_member = Mock()
        non_member.scalar.side_effect = [project(), employee(), None]
        with self.assertRaises(HTTPException) as member_error:
            get_project_employee_performance("BLI", EMPLOYEE_ID, non_member)
        self.assertEqual(member_error.exception.detail, "Project member not found")

    def test_sprint_report_enforces_project_scoped_sprint(self) -> None:
        db = Mock()
        db.scalar.side_effect = [project(), employee(), uuid.uuid4(), sprint()]
        expected = object()
        with patch("app.routers.employee_performance._build_report", return_value=expected) as build:
            result = get_sprint_employee_performance("BLI", SPRINT_ID, EMPLOYEE_ID, db)

        self.assertIs(result, expected)
        build.assert_called_once_with(db, project(), employee(), sprint=sprint())

        cross_project = Mock()
        cross_project.scalar.side_effect = [project(), employee(), uuid.uuid4(), None]
        with self.assertRaises(HTTPException) as error:
            get_sprint_employee_performance("BLI", SPRINT_ID, EMPLOYEE_ID, cross_project)
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Sprint not found")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
