from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import DocumentType
from app.routers import retrieval
from app.schemas.retrieval import SemanticSearchRequest, SemanticSearchResult
from app.services.retrieval_service import SemanticRetrievalError, SemanticRetrievalResult


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CHUNK_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="BLI")


def match() -> SemanticRetrievalResult:
    return SemanticRetrievalResult(
        document_id=DOCUMENT_ID,
        chunk_id=CHUNK_ID,
        chunk_index=2,
        document_title="Architecture",
        document_type=DocumentType.TRD,
        content="The platform isolates projects.",
        page_number=3,
        section_title="Security",
        metadata_json={"source_type": "pdf"},
        distance=0.18,
    )


class RetrievalRouterTests(unittest.TestCase):
    def test_request_validation_rejects_blank_query_and_invalid_top_k(self) -> None:
        for payload in (
            {"query": "  "},
            {"query": "security", "top_k": 0},
            {"query": "security", "top_k": 21},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    SemanticSearchRequest(**payload)

    def test_successful_search_returns_compact_results_without_vectors(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        request = SemanticSearchRequest(
            query="project isolation",
            top_k=3,
            document_types=[DocumentType.TRD],
        )
        with patch.object(retrieval, "search_project_documents", return_value=[match()]) as service:
            response = retrieval.search_project_documents_endpoint("BLI", request, db)

        service.assert_called_once_with(
            db=db,
            project_id=PROJECT_ID,
            query="project isolation",
            top_k=3,
            document_types=[DocumentType.TRD],
        )
        self.assertEqual(response.query, "project isolation")
        self.assertEqual(response.result_count, 1)
        self.assertEqual(response.results[0].chunk_id, CHUNK_ID)
        self.assertEqual(response.results[0].distance, 0.18)
        self.assertNotIn("embedding", SemanticSearchResult.model_fields)

    def test_empty_results_missing_project_and_controlled_failure(self) -> None:
        empty_db = Mock()
        empty_db.scalar.return_value = project()
        request = SemanticSearchRequest(query="nothing")
        with patch.object(retrieval, "search_project_documents", return_value=[]):
            response = retrieval.search_project_documents_endpoint("BLI", request, empty_db)
        self.assertEqual(response.result_count, 0)
        self.assertEqual(response.results, [])

        missing_db = Mock()
        missing_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as missing_project:
            retrieval.search_project_documents_endpoint("BLI", request, missing_db)
        self.assertEqual(missing_project.exception.status_code, 404)

        error_db = Mock()
        error_db.scalar.return_value = project()
        with patch.object(
            retrieval,
            "search_project_documents",
            side_effect=SemanticRetrievalError("synthetic internal failure"),
        ):
            with self.assertRaises(HTTPException) as service_error:
                retrieval.search_project_documents_endpoint("BLI", request, error_db)
        self.assertEqual(service_error.exception.status_code, 500)
        self.assertEqual(service_error.exception.detail, "Unable to retrieve document chunks")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
