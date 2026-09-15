from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import DocumentType
from app.routers import hybrid_evidence
from app.schemas.document_evidence import DocumentEvidenceResponse
from app.schemas.hybrid_evidence import HybridEvidenceRequest, HybridEvidenceResponse
from app.schemas.structured_evidence import StructuredEvidenceResponse
from app.services.hybrid_evidence_service import HybridEvidenceError, HybridEvidencePackage
from app.services.query_intent_service import QueryIntent


def package(intent: QueryIntent) -> HybridEvidencePackage:
    structured = SimpleNamespace(warnings=[]) if intent != QueryIntent.DOCUMENT else None
    document = SimpleNamespace(warnings=[]) if intent != QueryIntent.STRUCTURED else None
    return HybridEvidencePackage(
        query="evidence query", project_key="BLI", intent=intent,
        needs_structured_evidence=structured is not None,
        needs_document_evidence=document is not None,
        employee_reference="Sairaj" if structured else None,
        sprint_reference=None,
        requested_document_types=[DocumentType.PRD] if document else [],
        structured_evidence=structured,
        document_evidence=document,
        warnings=[],
    )


class HybridEvidenceRouterTests(unittest.TestCase):
    def test_structured_document_and_hybrid_responses_reuse_nested_converters(self) -> None:
        db = Mock()
        structured_response = StructuredEvidenceResponse.model_construct()
        document_response = DocumentEvidenceResponse.model_construct()
        for intent in (QueryIntent.STRUCTURED, QueryIntent.DOCUMENT, QueryIntent.HYBRID):
            with self.subTest(intent=intent), patch.object(
                hybrid_evidence, "build_hybrid_evidence", return_value=package(intent)
            ) as build, patch.object(
                hybrid_evidence, "structured_evidence_response", return_value=structured_response
            ) as structured_converter, patch.object(
                hybrid_evidence, "document_evidence_response", return_value=document_response
            ) as document_converter:
                response = hybrid_evidence.get_hybrid_evidence(
                    "BLI", HybridEvidenceRequest(query="evidence query"), db
                )

            self.assertIsInstance(response, HybridEvidenceResponse)
            self.assertEqual(response.intent, intent)
            self.assertEqual(response.structured_evidence is not None, intent != QueryIntent.DOCUMENT)
            self.assertEqual(response.document_evidence is not None, intent != QueryIntent.STRUCTURED)
            build.assert_called_once_with(db, "BLI", "evidence query", top_k=5)
            self.assertEqual(structured_converter.called, intent != QueryIntent.DOCUMENT)
            self.assertEqual(document_converter.called, intent != QueryIntent.STRUCTURED)
        self.assertNotIn("embedding", HybridEvidenceResponse.model_fields)

    def test_controlled_errors_blank_query_and_invalid_top_k(self) -> None:
        db = Mock()
        with patch.object(
            hybrid_evidence,
            "build_hybrid_evidence",
            side_effect=HybridEvidenceError("Project not found", status_code=404),
        ):
            with self.assertRaises(HTTPException) as missing:
                hybrid_evidence.get_hybrid_evidence("MISSING", HybridEvidenceRequest(query="issues"), db)
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as blank:
            hybrid_evidence.get_hybrid_evidence("BLI", HybridEvidenceRequest(query=" "), db)
        self.assertEqual(blank.exception.status_code, 422)

        for top_k in (0, 21):
            with self.subTest(top_k=top_k):
                with self.assertRaises(ValidationError):
                    HybridEvidenceRequest(query="issues", top_k=top_k)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
