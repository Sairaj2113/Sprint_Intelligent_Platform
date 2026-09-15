"""End-to-end deterministic checks for the Phase 9 evidence pipeline.

These tests intentionally keep the Phase 9A--9F services real.  The only
isolated boundary is ``embed_query``: a stable vector prevents a model load or
download while the real pgvector SQL statement is still built and passed to the
database session.  ``FixtureSession`` is a small in-memory stand-in for the
project's database fixture because these checks do not require a running
PostgreSQL service to validate orchestration and provenance.
"""

from __future__ import annotations

import re
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import DocumentType
from app.models.deployment import DeploymentStatus
from app.models.issue import IssueStatus, IssueType
from app.models.project import ProjectMethodology, ProjectStatus
from app.models.sprint import SprintStatus
from app.models.test_result import TestingStatus
from app.services.evidence_context_service import (
    EvidenceContextError,
    EvidenceContextLimits,
    build_evidence_context,
)
from app.services.evidence_source_service import EvidenceSourceType
from app.services.query_intent_service import QueryIntent


UTC = timezone.utc
VECTOR = [0.01] * 384


def _uuid(value: int) -> UUID:
    return UUID(int=value)


class _Rows:
    def __init__(self, rows: list[tuple[object, object, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, object, float]]:
        return self._rows


class FixtureSession:
    """Minimal deterministic Session substitute used only by this test module."""

    def __init__(
        self,
        *,
        project: SimpleNamespace | None,
        employees: list[SimpleNamespace] | None = None,
        sprints: list[SimpleNamespace] | None = None,
        issues: list[SimpleNamespace] | None = None,
        scoped_issues: list[SimpleNamespace] | None = None,
        employee_issues: list[SimpleNamespace] | None = None,
        histories: list[SimpleNamespace] | None = None,
        tests: list[SimpleNamespace] | None = None,
        deployments: list[SimpleNamespace] | None = None,
        comments: list[SimpleNamespace] | None = None,
        document_rows: list[tuple[object, object, float]] | None = None,
    ) -> None:
        self.project = project
        self.employees = employees or []
        self.sprints = sprints or []
        self.issues = issues or []
        self.scoped_issues = scoped_issues if scoped_issues is not None else self.issues
        self.employee_issues = employee_issues if employee_issues is not None else self.issues
        self.histories = histories or []
        self.tests = tests or []
        self.deployments = deployments or []
        self.comments = comments or []
        self.document_rows = document_rows or []
        self.scalar_statements: list[str] = []
        self.scalar_query_statements: list[str] = []
        self.execute_statement = ""

    def scalar(self, statement: object) -> SimpleNamespace | None:
        self.scalar_statements.append(str(statement))
        return self.project

    def scalars(self, statement: object) -> list[SimpleNamespace]:
        sql = str(statement)
        self.scalar_query_statements.append(sql)
        if "FROM employees" in sql:
            return self.employees
        if "FROM sprints" in sql:
            return self.sprints
        if "FROM issues" in sql:
            has_employee_scope = "issues.assignee_id" in sql
            has_sprint_scope = "issues.sprint_id" in sql
            if has_employee_scope and has_sprint_scope:
                return self.scoped_issues
            if has_employee_scope:
                return self.employee_issues
            return self.issues
        if "FROM issue_history" in sql:
            return self.histories
        if "FROM test_results" in sql:
            return self.tests
        if "FROM deployments" in sql:
            return self.deployments
        if "FROM comments" in sql:
            return self.comments
        raise AssertionError(f"Unexpected scalar query: {sql}")

    def execute(self, statement: object) -> _Rows:
        self.execute_statement = str(statement)
        limit_clause = getattr(statement, "_limit_clause", None)
        limit = getattr(limit_clause, "value", len(self.document_rows))
        return _Rows(self.document_rows[:limit])

    def close(self) -> None:
        pass


def _project(key: str, identifier: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=_uuid(identifier),
        project_key=key,
        name="Bank Loan Intelligence" if key == "BLI" else "RetailDialogue",
        status=ProjectStatus.ACTIVE,
        methodology=ProjectMethodology.SCRUM,
    )


def _issue(
    identifier: int,
    key: str,
    project_id: UUID,
    sprint_id: UUID,
    assignee_id: UUID,
    *,
    status: IssueStatus = IssueStatus.DONE,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=_uuid(identifier),
        issue_key=key,
        project_id=project_id,
        sprint_id=sprint_id,
        assignee_id=assignee_id,
        issue_type=IssueType.STORY,
        status=status,
        title=f"{key} implementation evidence",
        story_points=5,
        created_at=datetime(2026, 6, 1, 9, tzinfo=UTC),
        completed_at=datetime(2026, 6, 4, 17, tzinfo=UTC) if status == IssueStatus.DONE else None,
    )


def _history(identifier: int, issue_id: UUID, old: IssueStatus | None, new: IssueStatus, hour: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=_uuid(identifier),
        issue_id=issue_id,
        old_status=old,
        new_status=new,
        changed_at=datetime(2026, 6, 1, hour, tzinfo=UTC),
    )


def _document_rows(project_id: UUID) -> list[tuple[object, object, float]]:
    document = SimpleNamespace(
        id=_uuid(700), project_id=project_id, title="BLI Product Requirements", document_type=DocumentType.PRD
    )
    return [
        (
            SimpleNamespace(
                id=_uuid(701), project_id=project_id, document_id=document.id, chunk_index=0,
                content="Model approval requires documented validation evidence.", page_number=3,
                section_title="Model approval", metadata_json={"source": "fixture"},
            ),
            document,
            0.05,
        ),
        (
            SimpleNamespace(
                id=_uuid(702), project_id=project_id, document_id=document.id, chunk_index=1,
                content="The PRD requires traceable risk-model release criteria.", page_number=4,
                section_title="Release criteria", metadata_json={"source": "fixture"},
            ),
            document,
            0.12,
        ),
        (
            SimpleNamespace(
                id=_uuid(703), project_id=project_id, document_id=document.id, chunk_index=2,
                content="Approval records must identify the tested model version.", page_number=5,
                section_title="Governance", metadata_json={"source": "fixture"},
            ),
            document,
            0.21,
        ),
    ]


def _bli_session(*, include_documents: bool = True, empty: bool = False) -> FixtureSession:
    project = _project("BLI", 100)
    sairaju = SimpleNamespace(
        id=_uuid(101), employee_code="EMP001", name="Sairaj Pankar", role="Software Engineer", department="Engineering"
    )
    anjali = SimpleNamespace(
        id=_uuid(102), employee_code="EMP002", name="Anjali Sharma", role="Data Engineer", department="Data"
    )
    sprint_one = SimpleNamespace(
        id=_uuid(110), name="Foundation and Risk Model", status=SprintStatus.COMPLETED,
        start_date=date(2026, 6, 2), end_date=date(2026, 6, 13), created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    sprint_two = SimpleNamespace(
        id=_uuid(111), name="Assessment API and Dashboard", status=SprintStatus.COMPLETED,
        start_date=date(2026, 6, 16), end_date=date(2026, 6, 27), created_at=datetime(2026, 6, 15, tzinfo=UTC),
    )
    if empty:
        return FixtureSession(project=project, employees=[sairaju, anjali], sprints=[sprint_one, sprint_two])

    sprint_one_issue = _issue(201, "BLI-2", project.id, sprint_one.id, sairaju.id)
    sprint_two_issue = _issue(202, "BLI-15", project.id, sprint_two.id, sairaju.id)
    another_sprint_two_issue = _issue(203, "BLI-16", project.id, sprint_two.id, anjali.id)
    active_issue = _issue(204, "BLI-25", project.id, sprint_two.id, sairaju.id, status=IssueStatus.TESTING)
    issues = [sprint_one_issue, sprint_two_issue, another_sprint_two_issue, active_issue]
    histories = [
        _history(301, issue.id, None, IssueStatus.TODO, 9) for issue in issues
    ] + [
        _history(310, sprint_two_issue.id, IssueStatus.TODO, IssueStatus.IN_PROGRESS, 10),
        _history(311, sprint_two_issue.id, IssueStatus.IN_PROGRESS, IssueStatus.CODE_REVIEW, 11),
        _history(312, sprint_two_issue.id, IssueStatus.CODE_REVIEW, IssueStatus.TESTING, 12),
        _history(313, sprint_two_issue.id, IssueStatus.TESTING, IssueStatus.DONE, 13),
    ]
    test = SimpleNamespace(
        id=_uuid(401), issue_id=sprint_two_issue.id, testing_status=TestingStatus.PASSED,
        test_cases_total=10, test_cases_passed=10, bugs_found=0, reopened_count=0,
        tested_by=anjali.id, tested_at=datetime(2026, 6, 20, tzinfo=UTC),
    )
    deployment = SimpleNamespace(
        id=_uuid(501), issue_id=sprint_two_issue.id, deployment_status=DeploymentStatus.STAGING,
        environment="staging", deployment_date=datetime(2026, 6, 21, tzinfo=UTC),
        production_notes="Fixture deployment evidence", production_incidents=None,
    )
    comment = SimpleNamespace(
        id=_uuid(601), issue_id=sprint_two_issue.id, employee_id=sairaju.id,
        content="Fixture comment linked to the selected issue.", created_at=datetime(2026, 6, 21, tzinfo=UTC),
    )
    return FixtureSession(
        project=project,
        employees=[sairaju, anjali],
        sprints=[sprint_one, sprint_two],
        issues=issues,
        scoped_issues=[sprint_two_issue],
        employee_issues=[sprint_one_issue, sprint_two_issue, active_issue],
        histories=histories,
        tests=[test],
        deployments=[deployment],
        comments=[comment],
        document_rows=_document_rows(project.id) if include_documents else [],
    )


def _rd_session() -> FixtureSession:
    project = _project("RD", 900)
    employee = SimpleNamespace(
        id=_uuid(901), employee_code="EMP010", name="Retail Owner", role="Engineer", department="Engineering"
    )
    sprint = SimpleNamespace(
        id=_uuid(902), name="Retail Sprint 1", status=SprintStatus.ACTIVE,
        start_date=date(2026, 7, 1), end_date=date(2026, 7, 14), created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )
    issue = _issue(903, "RD-1", project.id, sprint.id, employee.id)
    return FixtureSession(project=project, employees=[employee], sprints=[sprint], issues=[issue])


def _source_pattern(source_type: EvidenceSourceType) -> str:
    return {
        EvidenceSourceType.ISSUE: r"ISSUE-[1-9]\d*",
        EvidenceSourceType.TEST: r"TEST-[1-9]\d*",
        EvidenceSourceType.DEPLOYMENT: r"DEPLOY-[1-9]\d*",
        EvidenceSourceType.COMMENT: r"COMMENT-[1-9]\d*",
        EvidenceSourceType.DOCUMENT: r"DOC-[1-9]\d*",
    }[source_type]


def _assert_stats(test_case: unittest.TestCase, context: object) -> None:
    stats = context.stats
    for category in ("issues", "tests", "deployments", "comments", "documents"):
        available = getattr(stats, f"available_{category}")
        included = getattr(stats, f"included_{category}")
        omitted = getattr(stats, f"omitted_{category}")
        test_case.assertEqual(available, included + omitted)
    test_case.assertEqual(stats.included_sources, len(context.sources))
    test_case.assertGreaterEqual(stats.available_sources, stats.included_sources)
    omitted_counts = [
        stats.omitted_issues, stats.omitted_tests, stats.omitted_deployments,
        stats.omitted_comments, stats.omitted_documents,
    ]
    test_case.assertEqual(stats.truncated, any(omitted_counts))


def _assert_source_integrity(test_case: unittest.TestCase, context: object) -> None:
    expected = {
        EvidenceSourceType.ISSUE: {item.id for item in context.issues},
        EvidenceSourceType.TEST: {item.id for item in context.tests},
        EvidenceSourceType.DEPLOYMENT: {item.id for item in context.deployments},
        EvidenceSourceType.COMMENT: {item.id for item in context.comments},
        EvidenceSourceType.DOCUMENT: {item.chunk_id for item in context.documents},
    }
    actual = {source_type: set() for source_type in EvidenceSourceType}
    source_ids = [source.source_id for source in context.sources]
    test_case.assertEqual(len(source_ids), len(set(source_ids)))
    for source in context.sources:
        test_case.assertTrue(source.source_id)
        test_case.assertRegex(source.source_id, _source_pattern(source.source_type))
        test_case.assertEqual(source.project_key, context.project_key)
        mapped_id = source.chunk_id if source.source_type == EvidenceSourceType.DOCUMENT else source.record_id
        test_case.assertIn(mapped_id, expected[source.source_type])
        actual[source.source_type].add(mapped_id)
    for source_type, identifiers in expected.items():
        test_case.assertEqual(actual[source_type], identifiers)


def _contains_embedding(value: object) -> bool:
    if isinstance(value, dict):
        return any(key.casefold() == "embedding" or _contains_embedding(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_embedding(item) for item in value)
    return False


def _contains_forbidden_decision_field(value: object) -> bool:
    forbidden = {
        "employee_score",
        "performance_score",
        "productivity_score",
        "rank",
        "ranking",
        "personality",
        "motivation",
    }
    if isinstance(value, dict):
        return any(
            key.casefold() in forbidden or _contains_forbidden_decision_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_decision_field(item) for item in value)
    return False


class HybridIntelligenceIntegrationTests(unittest.TestCase):
    """Exercise the production 9A--9F service chain with deterministic fixture data."""

    def _context(self, session: FixtureSession, query: str, **kwargs: object):
        with patch("app.services.retrieval_service.embed_query", return_value=VECTOR):
            return build_evidence_context(session, "BLI", query, **kwargs)

    def test_structured_query_resolves_employee_and_sprint_scope(self) -> None:
        session = _bli_session()
        context = self._context(session, "What did Sairaj contribute in Sprint 2?")

        self.assertEqual(context.intent, QueryIntent.STRUCTURED)
        self.assertEqual(context.employee_reference, "Sairaj")
        self.assertEqual(context.sprint_reference, "Sprint 2")
        self.assertEqual([issue.issue_key for issue in context.issues], ["BLI-15"])
        self.assertEqual(context.documents, [])
        self.assertEqual(context.issues[0].assignee_id, _uuid(101))
        self.assertEqual(context.issues[0].sprint_id, _uuid(111))
        self.assertTrue(any("issues.assignee_id" in sql and "issues.sprint_id" in sql for sql in session.scalar_query_statements))
        _assert_source_integrity(self, context)
        _assert_stats(self, context)

    def test_document_query_preserves_retrieval_order_and_document_provenance(self) -> None:
        session = _bli_session()
        with patch("app.services.retrieval_service.embed_query", return_value=VECTOR) as embed_query:
            context = build_evidence_context(
                session, "BLI", "What does the PRD require for model approval?", top_k=2
            )

        self.assertEqual(context.intent, QueryIntent.DOCUMENT)
        self.assertEqual(context.issues, [])
        self.assertEqual([item.chunk_index for item in context.documents], [0, 1])
        self.assertEqual([source.source_id for source in context.sources], ["DOC-1", "DOC-2"])
        self.assertTrue(all(source.source_type == EvidenceSourceType.DOCUMENT for source in context.sources))
        self.assertTrue(all(item.page_number is not None for item in context.documents))
        self.assertIn("documents.document_type", session.execute_statement)
        embed_query.assert_called_once_with("What does the PRD require for model approval?")
        _assert_source_integrity(self, context)
        _assert_stats(self, context)

    def test_hybrid_query_keeps_structured_document_sources_and_factual_warnings(self) -> None:
        context = self._context(
            _bli_session(), "What did Sairaj contribute toward the PRD model requirements?"
        )

        self.assertEqual(context.intent, QueryIntent.HYBRID)
        self.assertEqual(context.employee_reference, "Sairaj")
        self.assertTrue(context.issues)
        self.assertTrue(context.documents)
        self.assertIn(EvidenceSourceType.ISSUE, {source.source_type for source in context.sources})
        self.assertIn(EvidenceSourceType.DOCUMENT, {source.source_type for source in context.sources})
        self.assertNotIn("Evidence context was truncated by configured limits", context.warnings)
        self.assertFalse(any("score" in warning.casefold() or "rank" in warning.casefold() for warning in context.warnings))
        _assert_source_integrity(self, context)
        _assert_stats(self, context)

    def test_project_isolation_unknown_project_and_empty_evidence_are_controlled(self) -> None:
        bli = self._context(_bli_session(), "How many completed issues are there?")
        rd_session = _rd_session()
        with patch("app.services.retrieval_service.embed_query", return_value=VECTOR):
            rd = build_evidence_context(rd_session, "RD", "How many completed issues are there?")
        self.assertTrue(all(issue.issue_key.startswith("BLI-") for issue in bli.issues))
        self.assertTrue(all(issue.issue_key.startswith("RD-") for issue in rd.issues))
        self.assertEqual(rd.project_key, "RD")

        with self.assertRaises(EvidenceContextError) as error:
            self._context(FixtureSession(project=None), "How many completed issues are there?")
        self.assertEqual(error.exception.status_code, 404)

        empty = self._context(_bli_session(empty=True), "How many completed issues are there?")
        self.assertEqual(empty.issues, [])
        self.assertEqual(empty.sources, [])
        self.assertIn("Selected issue scope has no tests", empty.warnings)
        _assert_stats(self, empty)

    def test_restrictive_limits_remove_sources_without_renumbering_retained_ids(self) -> None:
        full = self._context(
            _bli_session(), "What did Sairaj contribute toward the PRD model requirements?", top_k=3
        )
        limits = EvidenceContextLimits(
            max_issues=1, max_tests=0, max_deployments=0, max_comments=0, max_documents=1
        )
        bounded = self._context(
            _bli_session(), "What did Sairaj contribute toward the PRD model requirements?", top_k=3, limits=limits
        )

        self.assertLessEqual(len(bounded.issues), 1)
        self.assertEqual(bounded.tests, [])
        self.assertEqual(bounded.deployments, [])
        self.assertEqual(bounded.comments, [])
        self.assertLessEqual(len(bounded.documents), 1)
        self.assertTrue(bounded.stats.truncated)
        self.assertEqual(bounded.warnings.count("Evidence context was truncated by configured limits"), 1)
        full_ids = {source.record_id or source.chunk_id: source.source_id for source in full.sources}
        for source in bounded.sources:
            self.assertEqual(full_ids[source.record_id or source.chunk_id], source.source_id)
        _assert_source_integrity(self, bounded)
        _assert_stats(self, bounded)

    def test_structured_and_document_results_are_deterministic(self) -> None:
        first = self._context(_bli_session(), "What did Sairaj contribute in Sprint 2?")
        second = self._context(_bli_session(), "What did Sairaj contribute in Sprint 2?")
        self.assertEqual(first.intent, second.intent)
        self.assertEqual(first.employee_reference, second.employee_reference)
        self.assertEqual(first.sprint_reference, second.sprint_reference)
        self.assertEqual([item.id for item in first.issues], [item.id for item in second.issues])
        self.assertEqual([source.source_id for source in first.sources], [source.source_id for source in second.sources])
        self.assertEqual(first.stats, second.stats)

        first_docs = self._context(_bli_session(), "What does the PRD require for model approval?")
        second_docs = self._context(_bli_session(), "What does the PRD require for model approval?")
        self.assertEqual([item.chunk_id for item in first_docs.documents], [item.chunk_id for item in second_docs.documents])
        self.assertEqual([source.source_id for source in first_docs.sources], [source.source_id for source in second_docs.sources])

    def test_endpoint_returns_bounded_context_without_embeddings_and_validates_input(self) -> None:
        def override_db(request: Request):
            if request.path_params["project_key"] == "UNKNOWN":
                yield FixtureSession(project=None)
            else:
                yield _bli_session()

        app.dependency_overrides[get_db] = override_db
        try:
            with patch("app.services.retrieval_service.embed_query", return_value=VECTOR):
                with TestClient(app) as client:
                    response = client.post(
                        "/projects/BLI/intelligence/context",
                        json={
                            "query": "What did Sairaj contribute toward the PRD model requirements?",
                            "top_k": 3,
                            "limits": {"max_issues": 2, "max_documents": 2},
                        },
                    )
                    missing = client.post(
                        "/projects/UNKNOWN/intelligence/context",
                        json={"query": "How many completed issues are there?"},
                    )
                    invalid = client.post(
                        "/projects/BLI/intelligence/context",
                        json={"query": "PRD requirements", "top_k": 21},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue({"query", "project_key", "intent", "issues", "tests", "deployments", "comments", "documents", "sources", "stats", "warnings"}.issubset(payload))
        self.assertEqual(payload["project_key"], "BLI")
        self.assertFalse(_contains_embedding(payload))
        self.assertFalse(_contains_forbidden_decision_field(payload))
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
