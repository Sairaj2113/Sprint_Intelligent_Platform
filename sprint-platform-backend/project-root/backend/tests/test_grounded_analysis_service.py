"""No-network unit tests for Phase 10G grounded-analysis orchestration."""

from __future__ import annotations

import copy
import unittest
from unittest.mock import Mock, patch

import app.services.llm.grounded_analysis_service as service
from app.services.llm.base import LLMGenerationResult, LLMUsage
from app.services.llm.citation_validator import CitationValidationResult
from app.services.llm.evidence_context_formatter import FormattedEvidenceContext
from app.services.llm.evidence_sufficiency import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyStatus,
)


QUESTION = "Who completed the persistence work?"
FORMATTED = FormattedEvidenceContext(
    text="PROJECT CONTEXT\nQuestion: Who completed the persistence work?\n\nISSUES\n- [ISSUE-2] BLI-15 | STORY | DONE",
    source_ids=("ISSUE-2", "TEST-4"),
    truncated=False,
)
VALID_JSON = """{
  "answer": "The persistence issue is recorded as done.",
  "claims": [{"statement": "BLI-15 is recorded as done.", "source_ids": ["ISSUE-2", "TEST-4"]}],
  "limitations": []
}"""
ABSTENTION_JSON = """{
  "answer": "The supplied evidence does not identify the deployment performer.",
  "claims": [],
  "limitations": ["Deployment evidence does not identify the person who performed it."]
}"""


class FakeLLMService:
    def __init__(self, content: str = VALID_JSON, *, fallback_used: bool = False) -> None:
        self.result = LLMGenerationResult(
            content=content,
            provider="gemini" if fallback_used else "groq",
            model="gemini-test" if fallback_used else "groq-test",
            fallback_used=fallback_used,
            usage=LLMUsage(input_tokens=12, output_tokens=9, total_tokens=21),
        )
        self.requests = []

    def generate(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return self.result


def citations(*, valid: bool = True) -> CitationValidationResult:
    return CitationValidationResult(
        valid=valid,
        cited_source_ids=("ISSUE-2",),
        valid_source_ids=("ISSUE-2",) if valid else (),
        invalid_source_ids=() if valid else ("DOC-99",),
    )


class GroundedAnalysisServiceTests(unittest.TestCase):
    def _analyze(self, llm: FakeLLMService | None = None, *, formatted: FormattedEvidenceContext = FORMATTED):
        llm = llm or FakeLLMService()
        with patch.object(service, "format_evidence_context", return_value=formatted) as formatter:
            result = service.analyze_grounded_question(QUESTION, Mock(name="bounded_context"), llm)
        return result, llm, formatter

    def test_blank_question_fails_before_formatter_or_llm(self) -> None:
        llm = FakeLLMService()
        with patch.object(service, "format_evidence_context") as formatter:
            with self.assertRaises(service.GroundedAnalysisError) as error:
                service.analyze_grounded_question("   ", Mock(), llm)

        self.assertEqual(error.exception.detail, "Question must not be blank")
        formatter.assert_not_called()
        self.assertEqual(llm.requests, [])

    def test_non_empty_evidence_formats_once_and_generates_once_with_deterministic_request(self) -> None:
        result, llm, formatter = self._analyze()

        formatter.assert_called_once()
        self.assertEqual(len(llm.requests), 1)
        request = llm.requests[0]
        self.assertEqual(request.temperature, 0)
        self.assertIsNone(request.max_output_tokens)
        self.assertIn("QUESTION\n\n" + QUESTION, request.user_prompt)
        self.assertIn("EVIDENCE\n\n" + FORMATTED.text, request.user_prompt)
        self.assertIn("ISSUE-2, TEST-4", request.user_prompt)
        self.assertIn("OUTPUT REQUIREMENTS", request.user_prompt)
        self.assertEqual(request.system_prompt, service.build_grounding_system_prompt())
        self.assertEqual(result.question, QUESTION)

    def test_valid_answer_preserves_claim_order_limitations_and_provider_metadata(self) -> None:
        result, _, _ = self._analyze()

        assert result.answer is not None
        self.assertEqual(result.answer.claims[0].source_ids, ["ISSUE-2", "TEST-4"])
        self.assertEqual(result.provider, "groq")
        self.assertEqual(result.model, "groq-test")
        self.assertFalse(result.fallback_used)
        self.assertEqual(result.usage, LLMUsage(input_tokens=12, output_tokens=9, total_tokens=21))

    def test_fallback_and_usage_metadata_are_preserved(self) -> None:
        result, _, _ = self._analyze(FakeLLMService(fallback_used=True))

        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "gemini-test")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.usage.total_tokens, 21)

    def test_validator_and_assessor_are_called_once_with_the_same_formatted_context(self) -> None:
        llm = FakeLLMService()
        validation = citations()
        sufficiency = EvidenceSufficiencyResult(EvidenceSufficiencyStatus.SUFFICIENT, True, (), ())
        with (
            patch.object(service, "format_evidence_context", return_value=FORMATTED),
            patch.object(service, "validate_answer_citations", return_value=validation) as validator,
            patch.object(service, "assess_evidence_sufficiency", return_value=sufficiency) as assessor,
        ):
            result = service.analyze_grounded_question(QUESTION, Mock(), llm)

        validator.assert_called_once()
        assessor.assert_called_once()
        self.assertIs(validator.call_args.args[1], FORMATTED)
        self.assertIs(assessor.call_args.args[1], FORMATTED)
        self.assertIs(assessor.call_args.args[2], validation)
        self.assertIs(result.evidence_sufficiency, sufficiency)

    def test_limited_zero_claim_abstention_flows_through_normal_pipeline(self) -> None:
        result, llm, _ = self._analyze(FakeLLMService(ABSTENTION_JSON))

        assert result.answer is not None
        self.assertEqual(result.answer.claims, [])
        self.assertEqual(result.evidence_sufficiency.status, EvidenceSufficiencyStatus.LIMITED)
        self.assertTrue(result.evidence_sufficiency.can_proceed)
        self.assertEqual(len(llm.requests), 1)

    def test_truncated_context_flows_to_limited_assessment(self) -> None:
        truncated = FormattedEvidenceContext(FORMATTED.text, FORMATTED.source_ids, truncated=True)
        result, _, _ = self._analyze(formatted=truncated)

        self.assertEqual(result.evidence_sufficiency.status, EvidenceSufficiencyStatus.LIMITED)
        self.assertIn("The supplied evidence context was truncated.", result.evidence_sufficiency.reasons)

    def test_invalid_citations_are_not_retried(self) -> None:
        llm = FakeLLMService(
            """{"answer":"Unsupported.","claims":[{"statement":"Unsupported.","source_ids":["DOC-99"]}],"limitations":[]}"""
        )
        result, _, _ = self._analyze(llm)

        self.assertEqual(result.evidence_sufficiency.status, EvidenceSufficiencyStatus.INVALID_CITATIONS)
        self.assertFalse(result.evidence_sufficiency.can_proceed)
        self.assertEqual(len(llm.requests), 1)

    def test_invalid_provider_output_is_controlled_and_is_not_retried(self) -> None:
        invalid_payloads = (
            "",
            "not json",
            "```json\n" + VALID_JSON + "\n```",
            "{\"answer\": \"Missing fields\", \"claims\": [], \"limitations\": [], \"extra\": true}",
            "{\"answer\": \"Bad source\", \"claims\": [{\"statement\": \"Bad\", \"source_ids\": [\"BAD-1\"]}], \"limitations\": []}",
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                llm = FakeLLMService(payload)
                with patch.object(service, "format_evidence_context", return_value=FORMATTED):
                    with self.assertRaises(service.GroundedAnalysisOutputError) as error:
                        service.analyze_grounded_question(QUESTION, Mock(), llm)
                self.assertEqual(error.exception.detail, "Unable to produce a valid grounded analysis")
                self.assertEqual(len(llm.requests), 1)

    def test_empty_evidence_short_circuits_without_fabricated_values(self) -> None:
        empty = FormattedEvidenceContext(text="bounded evidence", source_ids=(), truncated=False)
        result, llm, formatter = self._analyze(formatted=empty)

        formatter.assert_called_once()
        self.assertEqual(llm.requests, [])
        self.assertIsNone(result.answer)
        self.assertIsNone(result.citation_validation)
        self.assertIsNone(result.provider)
        self.assertIsNone(result.model)
        self.assertIsNone(result.fallback_used)
        self.assertIsNone(result.usage)
        self.assertEqual(result.evidence_sufficiency.status, EvidenceSufficiencyStatus.INSUFFICIENT)
        self.assertFalse(result.evidence_sufficiency.can_proceed)
        self.assertEqual(
            result.evidence_sufficiency.reasons,
            ("No evidence sources were supplied for grounded project-specific claims.",),
        )
        self.assertEqual(result.evidence_sufficiency.limitations, ())

    def test_inputs_are_not_mutated_and_fake_output_is_deterministic(self) -> None:
        context = Mock(name="bounded_context")
        before = copy.deepcopy(FORMATTED)
        first, _, _ = self._analyze()
        second, _, _ = self._analyze()

        self.assertEqual(first, second)
        self.assertEqual(FORMATTED, before)
        self.assertEqual(context.mock_calls, [])

    def test_module_has_no_direct_provider_database_or_retrieval_dependencies(self) -> None:
        self.assertEqual(
            service.GroundedAnalysisResult.__dataclass_fields__.keys(),
            {"question", "answer", "citation_validation", "evidence_sufficiency", "provider", "model", "fallback_used", "usage"},
        )
        for forbidden_name in (
            "GroqProvider", "GeminiProvider", "Session", "engine", "build_evidence_context",
            "build_hybrid_evidence", "search_project_documents", "embed_query", "requests", "httpx",
        ):
            self.assertFalse(hasattr(service, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
