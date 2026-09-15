from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.routers import evidence_context
from app.schemas.evidence_context import (
    BoundedEvidenceContextResponse,
    EvidenceContextRequest,
)
from app.services.evidence_context_service import (
    BoundedEvidenceContext,
    EvidenceContextError,
    EvidenceContextStats,
)
from app.services.query_intent_service import QueryIntent


def context() -> BoundedEvidenceContext:
    return BoundedEvidenceContext(
        query="requirements", project_key="BLI", intent=QueryIntent.DOCUMENT,
        employee_reference=None, sprint_reference=None,
        issues=[], tests=[], deployments=[], comments=[], documents=[], sources=[],
        stats=EvidenceContextStats(
            available_issues=1, included_issues=0, omitted_issues=1,
            available_tests=0, included_tests=0, omitted_tests=0,
            available_deployments=0, included_deployments=0, omitted_deployments=0,
            available_comments=0, included_comments=0, omitted_comments=0,
            available_documents=2, included_documents=1, omitted_documents=1,
            available_sources=3, included_sources=1, truncated=True,
        ),
        warnings=["Evidence context was truncated by configured limits"],
    )


class EvidenceContextRouterTests(unittest.TestCase):
    def test_default_custom_and_zero_limit_requests_return_bounded_schema(self) -> None:
        db = Mock()
        for request, expected_limits in (
            (EvidenceContextRequest(query="requirements"), None),
            (EvidenceContextRequest(query="requirements", limits={"max_issues": 2, "max_documents": 1}), {"max_issues": 2, "max_documents": 1}),
            (EvidenceContextRequest(query="requirements", limits={"max_comments": 0}), {"max_comments": 0}),
        ):
            with self.subTest(request=request), patch.object(evidence_context, "build_evidence_context", return_value=context()) as build:
                response = evidence_context.get_evidence_context("BLI", request, db)
            self.assertIsInstance(response, BoundedEvidenceContextResponse)
            self.assertEqual(response.stats.included_sources, 1)
            self.assertEqual(response.sources, [])
            actual_limits = build.call_args.kwargs["limits"]
            if expected_limits is None:
                self.assertIsNone(actual_limits)
            else:
                for field, value in expected_limits.items():
                    self.assertEqual(getattr(actual_limits, field), value)

    def test_invalid_payloads_and_controlled_errors(self) -> None:
        for limits in ({"max_comments": -1}, {"max_documents": 21}):
            with self.subTest(limits=limits):
                with self.assertRaises(ValidationError):
                    EvidenceContextRequest(query="requirements", limits=limits)
        for top_k in (0, 21):
            with self.subTest(top_k=top_k):
                with self.assertRaises(ValidationError):
                    EvidenceContextRequest(query="requirements", top_k=top_k)

        with patch.object(evidence_context, "build_evidence_context", side_effect=EvidenceContextError("Project not found", status_code=404)):
            with self.assertRaises(HTTPException) as error:
                evidence_context.get_evidence_context("MISSING", EvidenceContextRequest(query="requirements"), Mock())
        self.assertEqual(error.exception.status_code, 404)

        with patch.object(
            evidence_context,
            "build_evidence_context",
            side_effect=EvidenceContextError("Query must not be blank", status_code=422),
        ):
            with self.assertRaises(HTTPException) as blank:
                evidence_context.get_evidence_context("BLI", EvidenceContextRequest(query=" "), Mock())
        self.assertEqual(blank.exception.status_code, 422)
        self.assertNotIn("embedding", BoundedEvidenceContextResponse.model_fields)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
