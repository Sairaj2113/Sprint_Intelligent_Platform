"""Pure, attribution-safe tests for the Phase 14A contribution report."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.deployment import DeploymentStatus
from app.models.document import DocumentType
from app.models.issue import IssueStatus, IssueType
from app.models.requirement_trace_link import RequirementTraceLinkKind
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.services.employee_contribution_report_service import build_employee_contribution_report


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
EMPLOYEE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
OTHER_EMPLOYEE_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
SPRINT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
OTHER_SPRINT_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
NOW = datetime(2026, 10, 2, 9, tzinfo=timezone.utc)


def employee() -> SimpleNamespace:
    return SimpleNamespace(
        id=EMPLOYEE_ID,
        employee_code="EMP001",
        name="Sairaj Pankar",
        role="Engineer",
        department="Engineering",
    )


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="BLI", name="Bank Loan")


def sprint(identifier: uuid.UUID = SPRINT_ID, name: str = "Foundation") -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier,
        project_id=PROJECT_ID,
        name=name,
        status=SprintStatus.COMPLETED,
        start_date=NOW.date(),
    )


def issue(
    number: int,
    *,
    assignee_id: uuid.UUID | None = EMPLOYEE_ID,
    sprint_id: uuid.UUID | None = SPRINT_ID,
    status: IssueStatus = IssueStatus.DONE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(int=number),
        project_id=PROJECT_ID,
        issue_key=f"BLI-{number}",
        title=f"Issue {number}",
        issue_type=IssueType.TASK,
        assignee_id=assignee_id,
        sprint_id=sprint_id,
        status=status,
    )


def requirement(number: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(int=100 + number),
        project_id=PROJECT_ID,
        requirement_key=f"BLI-REQ-{number:03d}",
        statement=f"Requirement statement {number}",
    )


def trace(
    requirement_id: uuid.UUID,
    issue_id: uuid.UUID | None,
    *,
    project_id: uuid.UUID = PROJECT_ID,
    kind: RequirementTraceLinkKind = RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=project_id,
        requirement_id=requirement_id,
        issue_id=issue_id,
        link_kind=kind,
        verified_by_id=OTHER_EMPLOYEE_ID,
        verified_at=NOW,
    )


def report(
    issues: list[SimpleNamespace],
    *,
    comments: list[SimpleNamespace] | None = None,
    tests: list[SimpleNamespace] | None = None,
    deployments: list[SimpleNamespace] | None = None,
    links: list[SimpleNamespace] | None = None,
    requirements: dict[uuid.UUID, SimpleNamespace] | None = None,
    sources: dict[uuid.UUID, tuple[SimpleNamespace, SimpleNamespace]] | None = None,
    selected_sprint: SimpleNamespace | None = None,
):
    sprints = {SPRINT_ID: sprint(), OTHER_SPRINT_ID: sprint(OTHER_SPRINT_ID, "Hardening")}
    return build_employee_contribution_report(
        employee(), project(), issues, comments or [], tests or [], deployments or [], links or [],
        requirements or {}, sources or {}, sprints, sprint=selected_sprint,
    )


class EmployeeContributionReportServiceTests(unittest.TestCase):
    def test_project_scope_uses_current_assignment_and_current_done_semantics_only(self) -> None:
        assigned_done = issue(1, status=IssueStatus.DONE)
        assigned_open = issue(2, status=IssueStatus.IN_PROGRESS)
        other = issue(3, assignee_id=OTHER_EMPLOYEE_ID, status=IssueStatus.DONE)

        result = report([other, assigned_open, assigned_done])

        self.assertEqual([item.issue_key for item in result.currently_assigned_issues], ["BLI-1", "BLI-2"])
        self.assertEqual(result.currently_assigned_issue_keys_recorded_done, ["BLI-1"])
        self.assertTrue(all(item.attribution_basis.value == "CURRENT_ASSIGNMENT" for item in result.currently_assigned_issues))
        self.assertTrue(any("does not establish who completed" in item for item in result.limitations))
        self.assertFalse(any("completed by" in field for field in result.model_dump_json().casefold().splitlines()))

    def test_sprint_scope_requires_current_assignment_and_current_sprint_association(self) -> None:
        selected = sprint()
        in_scope = issue(1, sprint_id=SPRINT_ID)
        other_sprint = issue(2, sprint_id=OTHER_SPRINT_ID)
        unassigned = issue(3, assignee_id=OTHER_EMPLOYEE_ID, sprint_id=SPRINT_ID)

        result = report([in_scope, other_sprint, unassigned], selected_sprint=selected)

        self.assertEqual(result.scope.kind, "SPRINT")
        self.assertEqual([item.issue_key for item in result.currently_assigned_issues], ["BLI-1"])
        self.assertTrue(any("not historical sprint-membership" in item for item in result.limitations))

    def test_comments_are_direct_authorship_while_tests_and_deployments_are_only_linked_evidence(self) -> None:
        assigned = issue(1)
        other = issue(2, assignee_id=OTHER_EMPLOYEE_ID)
        comments = [
            SimpleNamespace(id=uuid.UUID(int=1), issue_id=assigned.id, employee_id=EMPLOYEE_ID, content="Mine", created_at=NOW),
            SimpleNamespace(id=uuid.UUID(int=2), issue_id=assigned.id, employee_id=OTHER_EMPLOYEE_ID, content="Other", created_at=NOW),
            SimpleNamespace(id=uuid.UUID(int=3), issue_id=other.id, employee_id=EMPLOYEE_ID, content="Project comment", created_at=NOW),
        ]
        tests = [
            SimpleNamespace(id=uuid.UUID(int=4), issue_id=assigned.id, testing_status=TestingStatus.PASSED,
                            test_cases_total=4, test_cases_passed=4, bugs_found=0, reopened_count=0,
                            testing_notes="Recorded", tested_at=NOW, tested_by=EMPLOYEE_ID),
            SimpleNamespace(id=uuid.UUID(int=5), issue_id=other.id, testing_status=TestingStatus.PASSED,
                            test_cases_total=1, test_cases_passed=1, bugs_found=0, reopened_count=0,
                            testing_notes=None, tested_at=NOW, tested_by=EMPLOYEE_ID),
        ]
        deployments = [
            SimpleNamespace(id=uuid.UUID(int=6), issue_id=assigned.id, deployment_status=DeploymentStatus.STAGING,
                            environment="staging", deployment_date=NOW, production_notes=None, production_incidents=None),
            SimpleNamespace(id=uuid.UUID(int=7), issue_id=other.id, deployment_status=DeploymentStatus.PRODUCTION,
                            environment="production", deployment_date=NOW, production_notes=None, production_incidents=None),
        ]

        result = report([assigned, other], comments=comments, tests=tests, deployments=deployments)

        self.assertEqual([item.content for item in result.authored_comments], ["Mine", "Project comment"])
        self.assertEqual([item.issue_key for item in result.linked_test_evidence], ["BLI-1"])
        self.assertEqual([item.issue_key for item in result.linked_deployment_evidence], ["BLI-1"])
        self.assertNotIn("tested_by", result.linked_test_evidence[0].model_dump())
        self.assertTrue(any("who performed testing" in item for item in result.limitations))
        self.assertTrue(any("who performed deployment" in item for item in result.limitations))

    def test_only_explicit_implemented_issue_trace_has_requirement_and_canonical_context(self) -> None:
        assigned = issue(11)
        unassigned = issue(12, assignee_id=OTHER_EMPLOYEE_ID)
        included_requirement = requirement(1)
        excluded_requirement = requirement(2)
        chunk = SimpleNamespace(id=uuid.UUID(int=201), chunk_index=3, page_number=2, section_title="Requirements", content="Canonical text")
        document = SimpleNamespace(id=uuid.UUID(int=202), title="BLI PRD", document_type=DocumentType.PRD)
        links = [
            trace(included_requirement.id, assigned.id),
            trace(excluded_requirement.id, unassigned.id),
            trace(included_requirement.id, assigned.id, kind=RequirementTraceLinkKind.VERIFIED_BY_TEST),
            trace(included_requirement.id, assigned.id, project_id=OTHER_PROJECT_ID),
        ]

        result = report(
            [assigned, unassigned],
            links=links,
            requirements={included_requirement.id: included_requirement, excluded_requirement.id: excluded_requirement},
            sources={included_requirement.id: (chunk, document)},
        )

        self.assertEqual([item.requirement_key for item in result.explicit_requirement_connections], ["BLI-REQ-001"])
        self.assertEqual(result.explicit_requirement_connections[0].issue_key, "BLI-11")
        self.assertEqual(result.explicit_requirement_connections[0].connection_basis.value, "EXPLICIT_REQUIREMENT_TRACE")
        self.assertEqual(result.explicit_requirement_connections[0].trace_verification.verified_by_id, OTHER_EMPLOYEE_ID)
        self.assertEqual([item.requirement_key for item in result.canonical_requirement_document_context], ["BLI-REQ-001"])
        self.assertEqual(result.canonical_requirement_document_context[0].context_basis.value, "CANONICAL_REQUIREMENT_SOURCE")
        self.assertTrue(any("requirement ownership" in item for item in result.limitations))

    def test_empty_current_assignment_and_unlinked_records_are_safe_and_deterministic(self) -> None:
        unassigned = issue(1, assignee_id=OTHER_EMPLOYEE_ID)
        first = report([unassigned])
        second = report([unassigned])

        self.assertEqual(first.model_dump(), second.model_dump())
        self.assertEqual(first.currently_assigned_issues, [])
        self.assertEqual(first.authored_comments, [])
        self.assertEqual(first.linked_test_evidence, [])
        self.assertEqual(first.linked_deployment_evidence, [])
        self.assertEqual(first.explicit_requirement_connections, [])
        self.assertTrue(any("Historical issue reassignment" in item for item in first.limitations))
        self.assertTrue(any("not a complete historical 'until now'" in item for item in first.limitations))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
