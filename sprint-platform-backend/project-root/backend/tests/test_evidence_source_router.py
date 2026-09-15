from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import DocumentType
from app.routers import evidence_source
from app.schemas.evidence_source import CitedEvidenceResponse, EvidenceSourceRead
from app.schemas.hybrid_evidence import HybridEvidenceRequest, HybridEvidenceResponse
from app.services.evidence_source_service import (
    CitedEvidencePackage,
    EvidenceSource,
    EvidenceSourceError,
    EvidenceSourceType,
)


def cited_package() -> CitedEvidencePackage:
    evidence = SimpleNamespace()
    source = EvidenceSource(
        source_id="DOC-1", source_type=EvidenceSourceType.DOCUMENT, project_key="BLI",
        record_id=uuid.uuid4(), title="BLI PRD", issue_key=None,
        document_id=uuid.uuid4(), chunk_id=uuid.uuid4(), chunk_index=0,
        document_type=DocumentType.PRD, page_number=3, section_title="Approval",
        metadata={"distance": 0.12},
    )
    return CitedEvidencePackage(evidence=evidence, sources=[source])


class EvidenceSourceRouterTests(unittest.TestCase):
    def test_successful_cited_response_reuses_hybrid_converter_and_excludes_embeddings(self) -> None:
        db = Mock()
        hybrid_response = HybridEvidenceResponse.model_construct()
        with patch.object(evidence_source, "build_cited_evidence", return_value=cited_package()) as build, patch.object(
            evidence_source, "hybrid_evidence_response", return_value=hybrid_response
        ) as converter:
            response = evidence_source.get_cited_evidence(
                "BLI", HybridEvidenceRequest(query="requirements"), db
            )

        self.assertIsInstance(response, CitedEvidenceResponse)
        self.assertEqual(response.source_count, 1)
        self.assertEqual(response.sources[0].source_id, "DOC-1")
        self.assertNotIn("embedding", EvidenceSourceRead.model_fields)
        build.assert_called_once_with(db, "BLI", "requirements", top_k=5)
        converter.assert_called_once()

    def test_controlled_error_blank_query_and_invalid_top_k(self) -> None:
        db = Mock()
        with patch.object(
            evidence_source,
            "build_cited_evidence",
            side_effect=EvidenceSourceError("Project not found", status_code=404),
        ):
            with self.assertRaises(HTTPException) as missing:
                evidence_source.get_cited_evidence("MISSING", HybridEvidenceRequest(query="issues"), db)
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as blank:
            evidence_source.get_cited_evidence("BLI", HybridEvidenceRequest(query=" "), db)
        self.assertEqual(blank.exception.status_code, 422)

        for top_k in (0, 21):
            with self.subTest(top_k=top_k):
                with self.assertRaises(ValidationError):
                    HybridEvidenceRequest(query="issues", top_k=top_k)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
