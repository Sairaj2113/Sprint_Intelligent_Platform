from __future__ import annotations

import unittest
import uuid
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import DocumentType
from app.routers import document_evidence
from app.schemas.document_evidence import (
    DocumentEvidenceItemRead,
    DocumentEvidenceRequest,
    DocumentEvidenceResponse,
)
from app.services.document_evidence_service import (
    DocumentEvidenceError,
    DocumentEvidenceItem,
    DocumentEvidencePackage,
)


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def package(results: list[DocumentEvidenceItem] | None = None) -> DocumentEvidencePackage:
    values = results or []
    return DocumentEvidencePackage(
        query="model requirements", project_id=PROJECT_ID, project_key="BLI",
        requested_document_types=[DocumentType.PRD], top_k=5,
        result_count=len(values), results=values,
        warnings=[] if values else ["No document evidence matched the requested document types"],
    )


def item() -> DocumentEvidenceItem:
    return DocumentEvidenceItem(
        document_id=DOCUMENT_ID, chunk_id=uuid.uuid4(), chunk_index=1,
        document_title="BLI PRD", document_type=DocumentType.PRD,
        content="Model approval evidence", page_number=8, section_title="Approval",
        metadata_json={"source_type": "pdf"}, distance=0.12,
    )


class DocumentEvidenceRouterTests(unittest.TestCase):
    def test_successful_and_filtered_response_reuses_document_evidence_service_only(self) -> None:
        db = Mock()
        request = DocumentEvidenceRequest(
            query="model requirements", top_k=5, document_types=[DocumentType.PRD]
        )
        with patch.object(document_evidence, "build_document_evidence", return_value=package([item()])) as build, patch(
            "app.services.structured_evidence_service.build_structured_evidence"
        ) as structured:
            response = document_evidence.get_document_evidence("BLI", request, db)

        self.assertIsInstance(response, DocumentEvidenceResponse)
        self.assertEqual(response.results[0].document_type, DocumentType.PRD)
        self.assertEqual(response.results[0].distance, 0.12)
        self.assertNotIn("embedding", DocumentEvidenceItemRead.model_fields)
        build.assert_called_once_with(
            db, "BLI", "model requirements", top_k=5, document_types=[DocumentType.PRD]
        )
        structured.assert_not_called()

    def test_empty_result_and_controlled_service_errors(self) -> None:
        db = Mock()
        with patch.object(document_evidence, "build_document_evidence", return_value=package()):
            response = document_evidence.get_document_evidence(
                "BLI", DocumentEvidenceRequest(query="missing"), db
            )
        self.assertEqual(response.result_count, 0)
        self.assertEqual(response.results, [])

        for status_code in (404, 422):
            with self.subTest(status_code=status_code), patch.object(
                document_evidence,
                "build_document_evidence",
                side_effect=DocumentEvidenceError("controlled", status_code=status_code),
            ):
                with self.assertRaises(HTTPException) as error:
                    document_evidence.get_document_evidence(
                        "BLI", DocumentEvidenceRequest(query="requirements"), db
                    )
            self.assertEqual(error.exception.status_code, status_code)

    def test_blank_query_and_invalid_top_k_are_rejected(self) -> None:
        with self.assertRaises(HTTPException) as blank:
            document_evidence.get_document_evidence(
                "BLI", DocumentEvidenceRequest(query="  "), Mock()
            )
        self.assertEqual(blank.exception.status_code, 422)

        for top_k in (0, 21):
            with self.subTest(top_k=top_k):
                with self.assertRaises(ValidationError):
                    DocumentEvidenceRequest(query="requirements", top_k=top_k)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
