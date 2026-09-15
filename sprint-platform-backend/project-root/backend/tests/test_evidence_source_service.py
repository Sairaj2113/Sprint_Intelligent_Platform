from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import DocumentType
from app.services import evidence_source_service as service
from app.services.hybrid_evidence_service import HybridEvidenceError


ISSUE_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TEST_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DEPLOYMENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
COMMENT_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
DOCUMENT_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
CHUNK_ONE_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
CHUNK_TWO_ID = uuid.UUID("77777777-7777-7777-7777-777777777777")


def issue(identifier: uuid.UUID = ISSUE_ID, key: str = "BLI-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier, issue_key=key, title="Platform setup", status="DONE", issue_type="TASK",
        story_points=3, sprint_id=None, sprint_name=None, assignee_id=None, assignee_name=None,
    )


def test(identifier: uuid.UUID = TEST_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier, issue_id=ISSUE_ID, testing_status="PASSED", test_cases_total=5,
        test_cases_passed=5, bugs_found=0, reopened_count=0, tested_by=None,
        tested_by_name=None, tested_at=None,
    )


def deployment(identifier: uuid.UUID = DEPLOYMENT_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier, issue_id=ISSUE_ID, deployment_status="STAGING", environment="staging",
        deployment_date=None, production_notes=None, production_incidents=None,
    )


def comment(identifier: uuid.UUID = COMMENT_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=identifier, issue_id=ISSUE_ID, employee_id=uuid.uuid4(), employee_name="Sairaj",
        content="Communication evidence", created_at=None,
    )


def document_result(chunk_id: uuid.UUID, index: int) -> SimpleNamespace:
    return SimpleNamespace(
        document_id=DOCUMENT_ID, chunk_id=chunk_id, chunk_index=index,
        document_title="BLI PRD", document_type=DocumentType.PRD,
        content=f"chunk content {index}", page_number=index + 1,
        section_title="Requirements", metadata_json={"source_type": "pdf", "content": "do not duplicate"}, distance=0.1 + index,
    )


def hybrid(
    *,
    structured: object | None = None,
    document: object | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(project_key="BLI", structured_evidence=structured, document_evidence=document)


class EvidenceSourceServiceTests(unittest.TestCase):
    def test_structured_sources_have_independent_deterministic_ids_and_metadata(self) -> None:
        structured = SimpleNamespace(
            issues=[issue(), issue(uuid.uuid4(), "BLI-2")],
            tests=[test()], deployments=[deployment()], comments=[comment()],
        )
        sources = service.build_evidence_sources(hybrid(structured=structured))

        self.assertEqual([source.source_id for source in sources], ["ISSUE-1", "ISSUE-2", "TEST-1", "DEPLOY-1", "COMMENT-1"])
        self.assertEqual(sources[0].record_id, ISSUE_ID)
        self.assertEqual(sources[0].issue_key, "BLI-1")
        self.assertEqual(sources[0].metadata["status"], "DONE")
        self.assertEqual(sources[2].metadata["issue_id"], ISSUE_ID)
        self.assertEqual(sources[3].metadata["environment"], "staging")
        self.assertEqual(sources[4].metadata["employee_name"], "Sairaj")

    def test_document_sources_follow_retrieval_order_and_do_not_duplicate_content(self) -> None:
        document = SimpleNamespace(results=[document_result(CHUNK_TWO_ID, 4), document_result(CHUNK_ONE_ID, 1)])
        sources = service.build_evidence_sources(hybrid(document=document))

        self.assertEqual([source.source_id for source in sources], ["DOC-1", "DOC-2"])
        self.assertEqual([source.chunk_id for source in sources], [CHUNK_TWO_ID, CHUNK_ONE_ID])
        self.assertEqual(sources[0].page_number, 5)
        self.assertEqual(sources[0].section_title, "Requirements")
        self.assertEqual(sources[0].document_type, DocumentType.PRD)
        self.assertEqual(sources[0].metadata["distance"], 4.1)
        self.assertNotIn("content", sources[0].metadata)
        self.assertFalse(hasattr(sources[0], "content"))

    def test_hybrid_preserves_first_occurrence_and_deduplicates_per_source_category(self) -> None:
        duplicate_issue = issue()
        duplicate_test = test()
        duplicate_deployment = deployment()
        duplicate_comment = comment()
        structured = SimpleNamespace(
            issues=[duplicate_issue, duplicate_issue], tests=[duplicate_test, duplicate_test],
            deployments=[duplicate_deployment, duplicate_deployment], comments=[duplicate_comment, duplicate_comment],
        )
        document = SimpleNamespace(
            results=[
                document_result(CHUNK_ONE_ID, 0), document_result(CHUNK_ONE_ID, 0),
                document_result(CHUNK_TWO_ID, 1),
            ]
        )
        sources = service.build_evidence_sources(hybrid(structured=structured, document=document))

        self.assertEqual([source.source_id for source in sources], ["ISSUE-1", "TEST-1", "DEPLOY-1", "COMMENT-1", "DOC-1", "DOC-2"])
        self.assertEqual([source.chunk_id for source in sources if source.chunk_id], [CHUNK_ONE_ID, CHUNK_TWO_ID])

    def test_lookup_and_no_io_boundary(self) -> None:
        db = Mock()
        sources = service.build_evidence_sources(hybrid(structured=SimpleNamespace(issues=[issue()], tests=[], deployments=[], comments=[])))

        self.assertEqual(service.get_source_by_id(sources, "ISSUE-1"), sources[0])
        self.assertIsNone(service.get_source_by_id(sources, "UNKNOWN"))
        db.assert_not_called()
        for forbidden_name in ("search_project_documents", "embed_query"):
            self.assertFalse(hasattr(service, forbidden_name), forbidden_name)
        self.assertFalse(any(source.source_type.value == "EMPLOYEE_SCORE" for source in sources))

    def test_cited_orchestration_calls_hybrid_once_and_translates_controlled_error(self) -> None:
        evidence = hybrid(structured=SimpleNamespace(issues=[issue()], tests=[], deployments=[], comments=[]))
        db = Mock()
        with patch.object(service, "build_hybrid_evidence", return_value=evidence) as build:
            package = service.build_cited_evidence(db, "BLI", "issues", top_k=3)
        build.assert_called_once_with(db, "BLI", "issues", top_k=3)
        self.assertEqual(package.source_count, 1)

        with patch.object(
            service, "build_hybrid_evidence", side_effect=HybridEvidenceError("Project not found", status_code=404)
        ):
            with self.assertRaises(service.EvidenceSourceError) as error:
                service.build_cited_evidence(db, "MISSING", "issues")
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
