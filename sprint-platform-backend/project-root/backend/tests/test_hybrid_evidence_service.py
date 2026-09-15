from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import DocumentType
from app.services import hybrid_evidence_service as service
from app.services.document_evidence_service import DocumentEvidenceError
from app.services.query_intent_service import QueryIntent, QueryIntentError, QueryIntentResult
from app.services.structured_evidence_service import StructuredEvidenceError


def intent(
    kind: QueryIntent,
    *,
    employee_reference: str | None = None,
    sprint_reference: str | None = None,
    document_types: list[DocumentType] | None = None,
) -> QueryIntentResult:
    return QueryIntentResult(
        query="What did Sairaj contribute toward the PRD requirements?",
        intent=kind,
        needs_structured_evidence=kind in (QueryIntent.STRUCTURED, QueryIntent.HYBRID),
        needs_document_evidence=kind in (QueryIntent.DOCUMENT, QueryIntent.HYBRID),
        employee_reference=employee_reference,
        sprint_reference=sprint_reference,
        document_types=document_types or [],
        matched_signals=["test"],
    )


class HybridEvidenceServiceTests(unittest.TestCase):
    def test_structured_intent_calls_only_structured_branch_and_preserves_query(self) -> None:
        structured_package = SimpleNamespace(warnings=["No tests"])
        db = Mock()
        with patch.object(service, "classify_query_intent", return_value=intent(QueryIntent.STRUCTURED, employee_reference="Sairaj", sprint_reference="Sprint 2")), patch.object(
            service, "build_structured_evidence", return_value=structured_package
        ) as structured, patch.object(service, "build_document_evidence_from_intent") as document:
            package = service.build_hybrid_evidence(db, "BLI", "What did Sairaj contribute?")

        structured.assert_called_once_with(
            db, "BLI", employee_reference="Sairaj", sprint_reference="Sprint 2"
        )
        document.assert_not_called()
        self.assertIs(package.structured_evidence, structured_package)
        self.assertIsNone(package.document_evidence)
        self.assertEqual(package.query, "What did Sairaj contribute toward the PRD requirements?")
        self.assertEqual(package.warnings, ["No tests"])

    def test_document_intent_calls_only_document_branch_with_top_k_and_types(self) -> None:
        document_package = SimpleNamespace(warnings=["No documents"])
        intent_result = intent(QueryIntent.DOCUMENT, document_types=[DocumentType.PRD])
        db = Mock()
        with patch.object(service, "classify_query_intent", return_value=intent_result), patch.object(
            service, "build_structured_evidence"
        ) as structured, patch.object(
            service, "build_document_evidence_from_intent", return_value=document_package
        ) as document:
            package = service.build_hybrid_evidence(db, "BLI", "What does the PRD require?", top_k=3)

        structured.assert_not_called()
        document.assert_called_once_with(db, "BLI", intent_result, top_k=3)
        self.assertIsNone(package.structured_evidence)
        self.assertIs(package.document_evidence, document_package)
        self.assertEqual(package.requested_document_types, [DocumentType.PRD])

    def test_hybrid_intent_calls_both_branches_and_deduplicates_warnings_in_order(self) -> None:
        structured_package = SimpleNamespace(warnings=["No tests", "No deployments"])
        document_package = SimpleNamespace(warnings=["No deployments", "No documents"])
        intent_result = intent(
            QueryIntent.HYBRID,
            employee_reference="Sairaj",
            sprint_reference="Sprint 3",
            document_types=[DocumentType.TRD],
        )
        db = Mock()
        with patch.object(service, "classify_query_intent", return_value=intent_result), patch.object(
            service, "build_structured_evidence", return_value=structured_package
        ) as structured, patch.object(
            service, "build_document_evidence_from_intent", return_value=document_package
        ) as document:
            package = service.build_hybrid_evidence(db, "BLI", "hybrid", top_k=4)

        structured.assert_called_once_with(
            db, "BLI", employee_reference="Sairaj", sprint_reference="Sprint 3"
        )
        document.assert_called_once_with(db, "BLI", intent_result, top_k=4)
        self.assertIs(package.structured_evidence, structured_package)
        self.assertIs(package.document_evidence, document_package)
        self.assertEqual(package.warnings, ["No tests", "No deployments", "No documents"])
        self.assertFalse(hasattr(package, "employee_rank"))
        self.assertFalse(hasattr(package, "performance_score"))

    def test_controlled_errors_translate_without_exposing_internal_details(self) -> None:
        db = Mock()
        with patch.object(service, "classify_query_intent", side_effect=QueryIntentError("Query must not be blank")):
            with self.assertRaises(service.HybridEvidenceError) as query_error:
                service.build_hybrid_evidence(db, "BLI", " ")
        self.assertEqual(query_error.exception.status_code, 422)

        with patch.object(service, "classify_query_intent", return_value=intent(QueryIntent.STRUCTURED)), patch.object(
            service, "build_structured_evidence", side_effect=StructuredEvidenceError("Project not found", status_code=404)
        ):
            with self.assertRaises(service.HybridEvidenceError) as structured_error:
                service.build_hybrid_evidence(db, "MISSING", "issues")
        self.assertEqual(structured_error.exception.status_code, 404)

        with patch.object(service, "classify_query_intent", return_value=intent(QueryIntent.DOCUMENT)), patch.object(
            service, "build_document_evidence_from_intent", side_effect=DocumentEvidenceError("Project not found", status_code=404)
        ):
            with self.assertRaises(service.HybridEvidenceError) as document_error:
                service.build_hybrid_evidence(db, "MISSING", "requirements")
        self.assertEqual(document_error.exception.status_code, 404)

    def test_service_has_no_direct_retrieval_embedding_or_metric_dependencies(self) -> None:
        for forbidden_name in (
            "search_project_documents",
            "embed_query",
            "calculate_issue_metrics",
            "build_employee_contribution_evidence",
            "build_workflow_evidence",
        ):
            self.assertFalse(hasattr(service, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
