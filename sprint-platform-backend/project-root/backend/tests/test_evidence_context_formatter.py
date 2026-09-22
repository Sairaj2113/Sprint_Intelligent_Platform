"""Pure, deterministic tests for Phase 10B evidence-context formatting."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from app.models import DocumentType
from app.models.issue import IssueStatus, IssueType
from app.services.evidence_context_service import BoundedEvidenceContext, EvidenceContextStats
from app.services.evidence_source_service import EvidenceSource, EvidenceSourceType
from app.services.llm.evidence_context_formatter import format_evidence_context
from app.services.query_intent_service import QueryIntent


UTC = timezone.utc
ISSUE_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_ID = UUID("22222222-2222-2222-2222-222222222222")
DEPLOY_ID = UUID("33333333-3333-3333-3333-333333333333")
COMMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
DOCUMENT_ID = UUID("55555555-5555-5555-5555-555555555555")
CHUNK_ONE_ID = UUID("66666666-6666-6666-6666-666666666666")
CHUNK_TWO_ID = UUID("77777777-7777-7777-7777-777777777777")


def _source(
    source_id: str,
    source_type: EvidenceSourceType,
    *,
    record_id: UUID | None = None,
    issue_key: str | None = None,
    document_id: UUID | None = None,
    chunk_id: UUID | None = None,
    chunk_index: int | None = None,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        source_type=source_type,
        project_key="BLI",
        record_id=record_id,
        title=source_id,
        issue_key=issue_key,
        document_id=document_id,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        document_type=DocumentType.PRD if source_type == EvidenceSourceType.DOCUMENT else None,
        page_number=3 if source_type == EvidenceSourceType.DOCUMENT else None,
        section_title="Model approval" if source_type == EvidenceSourceType.DOCUMENT else None,
        metadata={"embedding": [0.1, 0.2], "vector": "never serialize", "internal": "ignored"},
    )


def _issue() -> SimpleNamespace:
    return SimpleNamespace(
        id=ISSUE_ID, issue_key="BLI-15", title="Persist prediction results",
        issue_type=IssueType.STORY, status=IssueStatus.DONE, story_points=5,
        assignee_id=UUID("88888888-8888-8888-8888-888888888888"), assignee_name="Sairaj Pankar",
        sprint_id=UUID("99999999-9999-9999-9999-999999999999"), sprint_name="Sprint 2",
        created_at=datetime(2026, 6, 16, 9, tzinfo=UTC), completed_at=datetime(2026, 6, 20, 17, tzinfo=UTC),
    )


def _test() -> SimpleNamespace:
    return SimpleNamespace(
        id=TEST_ID, issue_id=ISSUE_ID, testing_status="PASSED", test_cases_total=10,
        test_cases_passed=10, bugs_found=0, reopened_count=0, tested_by=UUID(int=42),
        tested_by_name="Anjali Sharma", tested_at=datetime(2026, 6, 20, 14, tzinfo=UTC),
    )


def _deployment() -> SimpleNamespace:
    return SimpleNamespace(
        id=DEPLOY_ID, issue_id=ISSUE_ID, deployment_status="STAGING", environment="staging",
        deployment_date=datetime(2026, 6, 21, 10, tzinfo=UTC), production_notes="Validated deployment",
        production_incidents=None,
    )


def _comment() -> SimpleNamespace:
    return SimpleNamespace(
        id=COMMENT_ID, issue_id=ISSUE_ID, employee_id=UUID(int=43), employee_name="Sairaj Pankar",
        content="Persist the approved model version.", created_at=datetime(2026, 6, 21, 12, tzinfo=UTC),
    )


def _document(chunk_id: UUID, index: int, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        document_id=DOCUMENT_ID, chunk_id=chunk_id, chunk_index=index,
        document_title="BLI Product Requirements", document_type=DocumentType.PRD,
        content=content, page_number=index + 3, section_title="Model approval",
        metadata_json={"embedding": [0.1, 0.2], "vector": "never serialize"}, distance=0.1,
    )


def _stats(*, issues: int, tests: int, deployments: int, comments: int, documents: int, truncated: bool = False) -> EvidenceContextStats:
    return EvidenceContextStats(
        available_issues=issues, included_issues=issues, omitted_issues=0,
        available_tests=tests, included_tests=tests, omitted_tests=0,
        available_deployments=deployments, included_deployments=deployments, omitted_deployments=0,
        available_comments=comments, included_comments=comments, omitted_comments=0,
        available_documents=documents, included_documents=documents, omitted_documents=0,
        available_sources=issues + tests + deployments + comments + documents,
        included_sources=issues + tests + deployments + comments + documents,
        truncated=truncated,
    )


def _context(
    *,
    issues: list[SimpleNamespace] | None = None,
    tests: list[SimpleNamespace] | None = None,
    deployments: list[SimpleNamespace] | None = None,
    comments: list[SimpleNamespace] | None = None,
    documents: list[SimpleNamespace] | None = None,
    sources: list[EvidenceSource] | None = None,
    warnings: list[str] | None = None,
    truncated: bool = False,
) -> BoundedEvidenceContext:
    issues, tests, deployments, comments, documents = issues or [], tests or [], deployments or [], comments or [], documents or []
    return BoundedEvidenceContext(
        query="What evidence is available?", project_key="BLI", intent=QueryIntent.HYBRID,
        employee_reference="Sairaj", sprint_reference="Sprint 2", issues=issues, tests=tests,
        deployments=deployments, comments=comments, documents=documents, sources=sources or [],
        stats=_stats(issues=len(issues), tests=len(tests), deployments=len(deployments), comments=len(comments), documents=len(documents), truncated=truncated),
        warnings=warnings or [],
    )


class EvidenceContextFormatterTests(unittest.TestCase):
    def test_structured_only_evidence_uses_stable_source_identifiers(self) -> None:
        context = _context(
            issues=[_issue()], tests=[_test()], deployments=[_deployment()], comments=[_comment()],
            sources=[
                _source("ISSUE-4", EvidenceSourceType.ISSUE, record_id=ISSUE_ID, issue_key="BLI-15"),
                _source("TEST-3", EvidenceSourceType.TEST, record_id=TEST_ID, issue_key="BLI-15"),
                _source("DEPLOY-9", EvidenceSourceType.DEPLOYMENT, record_id=DEPLOY_ID, issue_key="BLI-15"),
                _source("COMMENT-2", EvidenceSourceType.COMMENT, record_id=COMMENT_ID, issue_key="BLI-15"),
            ],
        )

        formatted = format_evidence_context(context)

        self.assertEqual(formatted.source_ids, ("ISSUE-4", "TEST-3", "DEPLOY-9", "COMMENT-2"))
        self.assertIn("[ISSUE-4] BLI-15 | STORY | DONE", formatted.text)
        self.assertIn("[TEST-3] Issue ID:", formatted.text)
        self.assertIn("[DEPLOY-9] Issue ID:", formatted.text)
        self.assertIn("[COMMENT-2] Issue ID:", formatted.text)
        self.assertIn("2026-06-16T09:00:00+00:00", formatted.text)

    def test_document_only_evidence_preserves_semantic_retrieval_order(self) -> None:
        first = _document(CHUNK_TWO_ID, 4, "First retrieved document chunk")
        second = _document(CHUNK_ONE_ID, 1, "Second retrieved document chunk")
        context = _context(
            documents=[first, second],
            sources=[
                _source("DOC-7", EvidenceSourceType.DOCUMENT, record_id=CHUNK_ONE_ID, document_id=DOCUMENT_ID, chunk_id=CHUNK_ONE_ID, chunk_index=1),
                _source("DOC-3", EvidenceSourceType.DOCUMENT, record_id=CHUNK_TWO_ID, document_id=DOCUMENT_ID, chunk_id=CHUNK_TWO_ID, chunk_index=4),
            ],
        )

        formatted = format_evidence_context(context)

        self.assertEqual(formatted.source_ids, ("DOC-7", "DOC-3"))
        self.assertLess(formatted.text.index("[DOC-3]"), formatted.text.index("[DOC-7]"))
        self.assertLess(formatted.text.index("First retrieved document chunk"), formatted.text.index("Second retrieved document chunk"))

    def test_hybrid_output_has_fixed_sections_warnings_and_truncation(self) -> None:
        context = _context(
            issues=[_issue()], documents=[_document(CHUNK_ONE_ID, 1, "Requirement evidence")],
            sources=[
                _source("ISSUE-1", EvidenceSourceType.ISSUE, record_id=ISSUE_ID, issue_key="BLI-15"),
                _source("DOC-1", EvidenceSourceType.DOCUMENT, record_id=CHUNK_ONE_ID, document_id=DOCUMENT_ID, chunk_id=CHUNK_ONE_ID, chunk_index=1),
            ],
            warnings=["Selected issue scope has no tests", "Evidence context was truncated by configured limits"],
            truncated=True,
        )

        formatted = format_evidence_context(context)

        headings = ["PROJECT CONTEXT", "ISSUES", "TESTS", "DEPLOYMENTS", "COMMENTS", "DOCUMENT EVIDENCE", "CONTEXT STATUS", "WARNINGS"]
        self.assertEqual([formatted.text.index(heading) for heading in headings], sorted(formatted.text.index(heading) for heading in headings))
        self.assertTrue(formatted.truncated)
        self.assertIn("- Truncated: true", formatted.text)
        self.assertIn("- Selected issue scope has no tests", formatted.text)
        self.assertIn("- Evidence context was truncated by configured limits", formatted.text)

    def test_empty_context_is_valid_and_deterministic(self) -> None:
        context = _context()
        first = format_evidence_context(context)
        second = format_evidence_context(context)

        self.assertEqual(first, second)
        self.assertEqual(first.source_ids, ())
        self.assertFalse(first.truncated)
        self.assertIn("- No issue evidence.", first.text)
        self.assertIn("- No document evidence.", first.text)
        self.assertIn("- No warnings.", first.text)

    def test_metadata_vectors_and_external_services_are_not_exposed_or_called(self) -> None:
        context = _context(
            documents=[_document(CHUNK_ONE_ID, 1, "Safe document content")],
            sources=[_source("DOC-1", EvidenceSourceType.DOCUMENT, record_id=CHUNK_ONE_ID, document_id=DOCUMENT_ID, chunk_id=CHUNK_ONE_ID, chunk_index=1)],
        )

        formatted = format_evidence_context(context)

        self.assertNotIn("never serialize", formatted.text)
        self.assertNotIn("0.1, 0.2", formatted.text)
        self.assertNotIn("metadata_json", formatted.text)
        import app.services.llm.evidence_context_formatter as formatter
        for forbidden_name in ("LLMService", "GroqProvider", "GeminiProvider", "embed_query", "search_project_documents", "Session"):
            self.assertFalse(hasattr(formatter, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
