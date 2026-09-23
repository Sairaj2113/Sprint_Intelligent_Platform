"""TestClient coverage for the Phase 10H grounded-intelligence endpoint."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import DocumentType
from app.routers import evidence_context
from app.services.evidence_context_service import BoundedEvidenceContext, EvidenceContextError, EvidenceContextStats
from app.services.evidence_source_service import EvidenceSourceType
from app.services.llm.base import LLMNonRetryableError, LLMRetryableError, LLMUsage
from app.services.llm.citation_validator import CitationValidationResult
from app.services.llm.evidence_sufficiency import EvidenceSufficiencyResult, EvidenceSufficiencyStatus
from app.services.llm.grounded_analysis_service import (
    GroundedAnalysisOutputError,
    GroundedAnalysisResult,
)
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.query_intent_service import QueryIntent


ISSUE_ID = UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-2222-2222-222222222222")
CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeLLMService:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("The router must delegate generation to Phase 10G")


def bounded_context(*, sources: list[object] | None = None) -> BoundedEvidenceContext:
    source_items = sources or []
    return BoundedEvidenceContext(
        query="What did Sairaj contribute?",
        project_key="BLI",
        intent=QueryIntent.STRUCTURED,
        employee_reference="Sairaj",
        sprint_reference="Sprint 2",
        issues=[], tests=[], deployments=[], comments=[], documents=[], sources=source_items,  # type: ignore[arg-type]
        stats=EvidenceContextStats(
            available_issues=1, included_issues=1, omitted_issues=0,
            available_tests=0, included_tests=0, omitted_tests=0,
            available_deployments=0, included_deployments=0, omitted_deployments=0,
            available_comments=0, included_comments=0, omitted_comments=0,
            available_documents=1, included_documents=1, omitted_documents=0,
            available_sources=len(source_items), included_sources=len(source_items), truncated=False,
        ),
        warnings=[],
    )


def source(source_id: str, source_type: EvidenceSourceType, *, issue_key: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        source_id=source_id,
        source_type=source_type,
        title="BLI-15: Persist prediction results" if issue_key else "Architecture decision",
        issue_key=issue_key,
        record_id=ISSUE_ID if issue_key else CHUNK_ID,
        document_id=None if issue_key else DOCUMENT_ID,
        chunk_id=None if issue_key else CHUNK_ID,
        chunk_index=None if issue_key else 2,
        document_type=None if issue_key else DocumentType.ARCHITECTURE,
        page_number=None if issue_key else 4,
        section_title=None if issue_key else "Persistence",
        metadata={"embedding": [0.1], "vector": "hidden", "content": "not returned"},
    )


def result(
    status: EvidenceSufficiencyStatus = EvidenceSufficiencyStatus.SUFFICIENT,
    *,
    answer: GroundedAnswer | None = None,
    citation_validation: CitationValidationResult | None = None,
    provider: str | None = "groq",
    model: str | None = "openai/gpt-oss-20b",
    fallback_used: bool | None = False,
    usage: LLMUsage | None = LLMUsage(10, 8, 18),
) -> GroundedAnalysisResult:
    grounded_answer = answer or GroundedAnswer.model_validate(
        {
            "answer": "Sairaj is assigned to the recorded persistence issue.",
            "claims": [{"statement": "BLI-15 is done.", "source_ids": ["ISSUE-2", "DOC-4"]}],
            "limitations": ["The supplied evidence does not identify every implementation action."],
        }
    )
    validation = citation_validation or CitationValidationResult(
        valid=True,
        cited_source_ids=("ISSUE-2", "DOC-4"),
        valid_source_ids=("ISSUE-2", "DOC-4"),
        invalid_source_ids=(),
    )
    if status == EvidenceSufficiencyStatus.INSUFFICIENT:
        grounded_answer, validation, provider, model, fallback_used, usage = None, None, None, None, None, None
    return GroundedAnalysisResult(
        question="What did Sairaj contribute?",
        answer=grounded_answer,
        citation_validation=validation,
        evidence_sufficiency=EvidenceSufficiencyResult(
            status=status,
            can_proceed=status in {EvidenceSufficiencyStatus.SUFFICIENT, EvidenceSufficiencyStatus.LIMITED},
            reasons=() if status == EvidenceSufficiencyStatus.SUFFICIENT else ("A controlled condition applies.",),
            limitations=tuple(grounded_answer.limitations) if grounded_answer is not None else (),
        ),
        provider=provider,
        model=model,
        fallback_used=fallback_used,
        usage=usage,
    )


class GroundedAnalysisRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.llm = FakeLLMService()
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[evidence_context.get_llm_service] = lambda: self.llm
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        app.dependency_overrides.clear()

    def _post(self, payload: dict | None = None):
        return self.client.post(
            "/projects/BLI/intelligence/analyze",
            json=payload if payload is not None else {"question": "What did Sairaj contribute?"},
        )

    def test_success_serializes_answer_claim_order_validation_usage_and_safe_sources(self) -> None:
        context = bounded_context(sources=[source("ISSUE-2", EvidenceSourceType.ISSUE, issue_key="BLI-15"), source("DOC-4", EvidenceSourceType.DOCUMENT)])
        with (
            patch.object(evidence_context, "build_evidence_context", return_value=context) as build,
            patch.object(evidence_context, "analyze_grounded_question", return_value=result()) as analyze,
        ):
            response = self._post()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["question"], "What did Sairaj contribute?")
        self.assertEqual(body["answer"]["claims"][0]["source_ids"], ["ISSUE-2", "DOC-4"])
        self.assertEqual(body["answer"]["limitations"], ["The supplied evidence does not identify every implementation action."])
        self.assertEqual(body["citation_validation"]["valid_source_ids"], ["ISSUE-2", "DOC-4"])
        self.assertEqual(body["evidence"]["status"], "SUFFICIENT")
        self.assertEqual(body["generation"]["usage"]["total_tokens"], 18)
        self.assertEqual([item["source_id"] for item in body["sources"]], ["ISSUE-2", "DOC-4"])
        self.assertNotIn("metadata", body["sources"][0])
        self.assertNotIn("embedding", response.text)
        self.assertNotIn("vector", response.text)
        self.assertNotIn("content", body["sources"][1])
        build.assert_called_once()
        analyze.assert_called_once()
        self.assertEqual(build.call_args.args[2], "What did Sairaj contribute?")
        self.assertEqual(analyze.call_args.args[0], "What did Sairaj contribute?")
        self.assertEqual(self.llm.calls, 0)

    def test_limits_are_forwarded_and_existing_context_endpoint_remains_available(self) -> None:
        context = bounded_context()
        payload = {"question": "What did Sairaj contribute?", "top_k": 7, "limits": {"max_issues": 2, "max_documents": 1}}
        with (
            patch.object(evidence_context, "build_evidence_context", return_value=context) as build,
            patch.object(evidence_context, "analyze_grounded_question", return_value=result()),
        ):
            response = self._post(payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(build.call_args.kwargs["top_k"], 7)
        limits = build.call_args.kwargs["limits"]
        self.assertEqual(limits.max_issues, 2)
        self.assertEqual(limits.max_documents, 1)

        with patch.object(evidence_context, "build_evidence_context", return_value=context):
            context_response = self.client.post("/projects/BLI/intelligence/context", json={"query": "requirements"})
        self.assertEqual(context_response.status_code, 200)

    def test_limited_and_invalid_citation_results_are_successful_without_regeneration(self) -> None:
        context = bounded_context()
        invalid = CitationValidationResult(False, ("DOC-99",), (), ("DOC-99",))
        cases = (
            (EvidenceSufficiencyStatus.LIMITED, result(EvidenceSufficiencyStatus.LIMITED), True),
            (EvidenceSufficiencyStatus.INVALID_CITATIONS, result(EvidenceSufficiencyStatus.INVALID_CITATIONS, citation_validation=invalid), False),
        )
        for expected_status, analysis_result, can_proceed in cases:
            with self.subTest(status=expected_status):
                with (
                patch.object(evidence_context, "build_evidence_context", return_value=context),
                patch.object(evidence_context, "analyze_grounded_question", return_value=analysis_result) as analyze,
                ):
                    response = self._post()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["evidence"]["status"], expected_status.value)
            self.assertEqual(response.json()["evidence"]["can_proceed"], can_proceed)
            analyze.assert_called_once()
            self.assertEqual(self.llm.calls, 0)

    def test_empty_evidence_returns_successful_insufficient_result_with_null_generation(self) -> None:
        context = bounded_context()
        with (
            patch.object(evidence_context, "build_evidence_context", return_value=context),
            patch.object(evidence_context, "analyze_grounded_question", return_value=result(EvidenceSufficiencyStatus.INSUFFICIENT)) as analyze,
        ):
            response = self._post()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["answer"])
        self.assertIsNone(body["citation_validation"])
        self.assertEqual(body["evidence"]["status"], "INSUFFICIENT")
        self.assertFalse(body["evidence"]["can_proceed"])
        self.assertEqual(body["generation"], {"provider": None, "model": None, "fallback_used": None, "usage": None})
        self.assertEqual(body["sources"], [])
        analyze.assert_called_once()
        self.assertEqual(self.llm.calls, 0)

    def test_request_validation_rejects_blank_malformed_and_out_of_range_values(self) -> None:
        cases = (
            {"question": "   "},
            {},
            {"question": "valid", "top_k": 0},
            {"question": "valid", "top_k": 21},
            {"question": "valid", "limits": {"max_documents": 21}},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                response = self._post(payload)
                self.assertEqual(response.status_code, 422)

    def test_controlled_context_and_generation_errors_have_safe_statuses_and_bodies(self) -> None:
        cases = (
            (EvidenceContextError("Project not found", status_code=404), 404, "Project not found"),
            (GroundedAnalysisOutputError(), 502, "Unable to produce a valid grounded analysis"),
            (LLMRetryableError("gemini", "secret provider detail"), 503, "Grounded analysis provider is temporarily unavailable"),
            (LLMNonRetryableError("groq", "secret provider detail"), 502, "Unable to generate grounded analysis"),
        )
        for error, expected_status, expected_detail in cases:
            with self.subTest(error=error):
                if isinstance(error, EvidenceContextError):
                    context_patch = patch.object(evidence_context, "build_evidence_context", side_effect=error)
                    analyze_patch = patch.object(evidence_context, "analyze_grounded_question")
                else:
                    context_patch = patch.object(evidence_context, "build_evidence_context", return_value=bounded_context())
                    analyze_patch = patch.object(evidence_context, "analyze_grounded_question", side_effect=error)
                with context_patch, analyze_patch:
                    response = self._post()
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.json(), {"detail": expected_detail})
                self.assertNotIn("secret provider detail", response.text)

    def test_router_does_not_import_or_call_provider_adapters_directly(self) -> None:
        for forbidden_name in ("GroqProvider", "GeminiProvider", "embed_query", "search_project_documents"):
            self.assertFalse(hasattr(evidence_context, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
