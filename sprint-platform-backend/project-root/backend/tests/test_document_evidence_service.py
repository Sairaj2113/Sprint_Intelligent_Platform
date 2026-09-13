from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from app.models import DocumentType
from app.services import document_evidence_service as service
from app.services.document_evidence_service import DocumentEvidenceError
from app.services.query_intent_service import QueryIntent, QueryIntentResult
from app.services.retrieval_service import SemanticRetrievalResult


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="BLI")


def result(index: int, document_type: DocumentType = DocumentType.PRD) -> SemanticRetrievalResult:
    return SemanticRetrievalResult(
        document_id=DOCUMENT_ID,
        chunk_id=uuid.uuid4(),
        chunk_index=index,
        document_title="BLI PRD",
        document_type=document_type,
        content=f"evidence {index}",
        page_number=index + 1,
        section_title="Requirements",
        metadata_json={"source_type": "pdf"},
        distance=0.1 + index,
    )


class DocumentEvidenceServiceTests(unittest.TestCase):
    def _db(self, project_value: object | None = None) -> Mock:
        db = Mock()
        db.scalar.return_value = None if project_value is False else (
            project() if project_value is None else project_value
        )
        return db

    def test_project_wide_retrieval_reuses_search_once_and_preserves_order_metadata(self) -> None:
        db = self._db()
        retrieved = [result(2), result(0)]
        with patch.object(service, "search_project_documents", return_value=retrieved) as search, patch(
            "app.services.embedding_service.embed_query"
        ) as embed_query:
            package = service.build_document_evidence(db, "BLI", "model requirements", top_k=2)

        search.assert_called_once_with(
            db=db,
            project_id=PROJECT_ID,
            query="model requirements",
            top_k=2,
            document_types=None,
        )
        embed_query.assert_not_called()
        self.assertEqual([item.chunk_index for item in package.results], [2, 0])
        self.assertEqual(package.results[0].metadata_json, {"source_type": "pdf"})
        self.assertEqual(package.results[0].distance, 2.1)
        self.assertEqual(package.requested_document_types, [])

    def test_prd_and_trd_filters_are_forwarded_without_automatic_defaults(self) -> None:
        for document_type in (DocumentType.PRD, DocumentType.TRD):
            with self.subTest(document_type=document_type):
                db = self._db()
                with patch.object(service, "search_project_documents", return_value=[]) as search:
                    package = service.build_document_evidence(
                        db, "BLI", "requirements", document_types=[document_type]
                    )
                self.assertEqual(package.requested_document_types, [document_type])
                self.assertEqual(search.call_args.kwargs["document_types"], [document_type])

    def test_empty_results_have_factual_general_and_filter_warnings(self) -> None:
        with patch.object(service, "search_project_documents", return_value=[]):
            unfiltered = service.build_document_evidence(self._db(), "BLI", "requirements")
        self.assertEqual(unfiltered.warnings, ["Document retrieval returned no evidence"])

        with patch.object(service, "search_project_documents", return_value=[]):
            filtered = service.build_document_evidence(
                self._db(), "BLI", "requirements", document_types=[DocumentType.PRD]
            )
        self.assertEqual(
            filtered.warnings,
            ["No document evidence matched the requested document types"],
        )

    def test_project_query_and_top_k_validation_errors_are_controlled(self) -> None:
        missing_db = self._db(project_value=False)
        with self.assertRaises(DocumentEvidenceError) as missing:
            service.build_document_evidence(missing_db, "MISSING", "requirements")
        self.assertEqual(missing.exception.status_code, 404)

        for query, top_k in (("  ", 5), ("requirements", 0), ("requirements", 21)):
            with self.subTest(query=query, top_k=top_k):
                with self.assertRaises(DocumentEvidenceError):
                    service.build_document_evidence(self._db(), "BLI", query, top_k=top_k)

    def test_intent_helper_skips_structured_and_forwards_document_and_hybrid_hints(self) -> None:
        structured = QueryIntentResult(
            query="How many issues are open?", intent=QueryIntent.STRUCTURED,
            needs_structured_evidence=True, needs_document_evidence=False,
            employee_reference=None, sprint_reference=None, document_types=[], matched_signals=["issues"],
        )
        self.assertIsNone(service.build_document_evidence_from_intent(self._db(), "BLI", structured))

        for intent in (QueryIntent.DOCUMENT, QueryIntent.HYBRID):
            with self.subTest(intent=intent):
                intent_result = QueryIntentResult(
                    query="What does the PRD require?", intent=intent,
                    needs_structured_evidence=intent == QueryIntent.HYBRID,
                    needs_document_evidence=True, employee_reference=None, sprint_reference=None,
                    document_types=[DocumentType.PRD], matched_signals=["prd"],
                )
                with patch.object(service, "build_document_evidence", return_value=Mock()) as build:
                    service.build_document_evidence_from_intent(self._db(), "BLI", intent_result, top_k=3)
                build.assert_called_once_with(
                    ANY,
                    "BLI",
                    "What does the PRD require?",
                    top_k=3,
                    document_types=[DocumentType.PRD],
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
