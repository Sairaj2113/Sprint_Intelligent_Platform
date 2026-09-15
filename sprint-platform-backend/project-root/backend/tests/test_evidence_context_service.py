from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import DocumentType
from app.services import evidence_context_service as service
from app.services.evidence_source_service import (
    CitedEvidencePackage,
    EvidenceSource,
    EvidenceSourceError,
    EvidenceSourceType,
)
from app.services.query_intent_service import QueryIntent


def structured_item(identifier: uuid.UUID, kind: str, index: int) -> SimpleNamespace:
    common = {"id": identifier}
    if kind == "issue":
        return SimpleNamespace(**common, issue_key=f"BLI-{index}", title="Issue", issue_type="TASK", status="TODO", story_points=None, assignee_id=None, assignee_name=None, sprint_id=None, sprint_name=None, created_at=None, completed_at=None)
    if kind == "test":
        return SimpleNamespace(**common, issue_id=uuid.uuid4(), testing_status="PASSED", test_cases_total=None, test_cases_passed=None, bugs_found=None, reopened_count=None, tested_by=None, tested_by_name=None, tested_at=None)
    if kind == "deployment":
        return SimpleNamespace(**common, issue_id=uuid.uuid4(), deployment_status="STAGING", environment=None, deployment_date=None, production_notes=None, production_incidents=None)
    return SimpleNamespace(**common, issue_id=uuid.uuid4(), employee_id=uuid.uuid4(), employee_name=None, content="comment", created_at=None)


def document_item(identifier: uuid.UUID, index: int) -> SimpleNamespace:
    return SimpleNamespace(
        document_id=uuid.uuid4(), chunk_id=identifier, chunk_index=index,
        document_title="PRD", document_type=DocumentType.PRD, content=f"content {index}",
        page_number=index + 1, section_title="Section", metadata_json={}, distance=float(index),
    )


def source(source_type: EvidenceSourceType, identifier: uuid.UUID, label: str) -> EvidenceSource:
    return EvidenceSource(
        source_id=label, source_type=source_type, project_key="BLI", record_id=identifier,
        title=label, issue_key=None, document_id=None,
        chunk_id=identifier if source_type == EvidenceSourceType.DOCUMENT else None,
        chunk_index=None, document_type=DocumentType.PRD if source_type == EvidenceSourceType.DOCUMENT else None,
        page_number=None, section_title=None, metadata={},
    )


def cited() -> CitedEvidencePackage:
    issues = [structured_item(uuid.uuid4(), "issue", index) for index in range(3)]
    tests = [structured_item(uuid.uuid4(), "test", index) for index in range(2)]
    deployments = [structured_item(uuid.uuid4(), "deployment", index) for index in range(2)]
    comments = [structured_item(uuid.uuid4(), "comment", index) for index in range(2)]
    documents = [document_item(uuid.uuid4(), index) for index in range(4)]
    structured = SimpleNamespace(issues=issues, tests=tests, deployments=deployments, comments=comments)
    document = SimpleNamespace(results=documents)
    evidence = SimpleNamespace(
        query="requirements", project_key="BLI", intent=QueryIntent.HYBRID,
        employee_reference="Sairaj", sprint_reference="Sprint 2", warnings=["Existing warning"],
        structured_evidence=structured, document_evidence=document,
    )
    sources = [
        *[source(EvidenceSourceType.ISSUE, item.id, f"ISSUE-{index + 1}") for index, item in enumerate(issues)],
        *[source(EvidenceSourceType.TEST, item.id, f"TEST-{index + 1}") for index, item in enumerate(tests)],
        *[source(EvidenceSourceType.DEPLOYMENT, item.id, f"DEPLOY-{index + 1}") for index, item in enumerate(deployments)],
        *[source(EvidenceSourceType.COMMENT, item.id, f"COMMENT-{index + 1}") for index, item in enumerate(comments)],
        *[source(EvidenceSourceType.DOCUMENT, item.chunk_id, f"DOC-{index + 1}") for index, item in enumerate(documents)],
    ]
    return CitedEvidencePackage(evidence=evidence, sources=sources)


class EvidenceContextServiceTests(unittest.TestCase):
    def test_default_limits_custom_limits_and_original_package_are_preserved(self) -> None:
        original = cited()
        context = service.build_bounded_evidence_context(original)
        self.assertEqual(context.stats.available_issues, 3)
        self.assertEqual(context.stats.included_issues, 3)
        self.assertFalse(context.stats.truncated)
        self.assertEqual(len(original.evidence.document_evidence.results), 4)

        limits = service.EvidenceContextLimits(
            max_issues=2, max_tests=1, max_deployments=1, max_comments=1, max_documents=2
        )
        bounded = service.build_bounded_evidence_context(original, limits=limits)
        self.assertEqual([item.id for item in bounded.issues], [item.id for item in original.evidence.structured_evidence.issues[:2]])
        self.assertEqual([item.chunk_id for item in bounded.documents], [item.chunk_id for item in original.evidence.document_evidence.results[:2]])
        self.assertEqual(bounded.stats.omitted_issues, 1)
        self.assertEqual(bounded.stats.omitted_tests, 1)
        self.assertEqual(bounded.stats.omitted_deployments, 1)
        self.assertEqual(bounded.stats.omitted_comments, 1)
        self.assertEqual(bounded.stats.omitted_documents, 2)
        self.assertTrue(bounded.stats.truncated)
        self.assertEqual(bounded.warnings, ["Existing warning", "Evidence context was truncated by configured limits"])
        self.assertEqual([source.source_id for source in bounded.sources], ["ISSUE-1", "ISSUE-2", "TEST-1", "DEPLOY-1", "COMMENT-1", "DOC-1", "DOC-2"])

    def test_zero_limits_remove_matching_sources_without_renumbering(self) -> None:
        original = cited()
        context = service.build_bounded_evidence_context(
            original,
            limits=service.EvidenceContextLimits(
                max_issues=0, max_tests=0, max_deployments=0, max_comments=0, max_documents=0
            ),
        )
        self.assertEqual(context.issues, [])
        self.assertEqual(context.tests, [])
        self.assertEqual(context.deployments, [])
        self.assertEqual(context.comments, [])
        self.assertEqual(context.documents, [])
        self.assertEqual(context.sources, [])
        self.assertEqual(context.stats.included_sources, 0)
        self.assertEqual(context.stats.omitted_comments, 2)
        self.assertTrue(context.stats.truncated)

    def test_source_matching_uses_identity_not_positions_and_document_rank_is_unchanged(self) -> None:
        original = cited()
        reordered_sources = list(reversed(original.sources))
        reordered = CitedEvidencePackage(evidence=original.evidence, sources=reordered_sources)
        context = service.build_bounded_evidence_context(
            reordered,
            limits=service.EvidenceContextLimits(max_issues=1, max_tests=1, max_deployments=1, max_comments=1, max_documents=2),
        )
        retained_ids = {source.record_id for source in context.sources if source.source_type != EvidenceSourceType.DOCUMENT}
        self.assertIn(original.evidence.structured_evidence.issues[0].id, retained_ids)
        self.assertEqual([item.chunk_index for item in context.documents], [0, 1])
        self.assertEqual({source.source_id for source in context.sources if source.source_type == EvidenceSourceType.DOCUMENT}, {"DOC-1", "DOC-2"})

    def test_invalid_limits_and_end_to_end_builder_are_controlled(self) -> None:
        with self.assertRaises(service.EvidenceContextError):
            service.EvidenceContextLimits(max_comments=-1)
        with self.assertRaises(service.EvidenceContextError):
            service.EvidenceContextLimits(max_documents=21)

        db = Mock()
        original = cited()
        with patch.object(service, "build_cited_evidence", return_value=original) as build:
            context = service.build_evidence_context(db, "BLI", "requirements", top_k=10, limits=service.EvidenceContextLimits(max_documents=2))
        build.assert_called_once_with(db, "BLI", "requirements", top_k=10)
        self.assertEqual(len(context.documents), 2)
        self.assertEqual(len(original.evidence.document_evidence.results), 4)

        with patch.object(service, "build_cited_evidence", side_effect=EvidenceSourceError("Project not found", status_code=404)):
            with self.assertRaises(service.EvidenceContextError) as error:
                service.build_evidence_context(db, "MISSING", "requirements")
        self.assertEqual(error.exception.status_code, 404)

    def test_service_has_no_direct_lower_layer_dependencies(self) -> None:
        for forbidden_name in (
            "classify_query_intent", "build_structured_evidence", "build_document_evidence",
            "search_project_documents", "embed_query", "build_hybrid_evidence",
            "calculate_issue_metrics", "build_employee_contribution_evidence", "build_workflow_evidence",
        ):
            self.assertFalse(hasattr(service, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
