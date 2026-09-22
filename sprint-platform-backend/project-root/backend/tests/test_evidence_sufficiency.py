"""Pure deterministic tests for Phase 10F evidence-condition assessment."""

from __future__ import annotations

import copy
import unittest
from dataclasses import FrozenInstanceError

import app.services.llm.evidence_sufficiency as evidence_sufficiency
from app.services.llm.citation_validator import CitationValidationResult
from app.services.llm.evidence_context_formatter import FormattedEvidenceContext
from app.services.llm.grounded_answer import GroundedAnswer


def context(*source_ids: str, truncated: bool = False) -> FormattedEvidenceContext:
    return FormattedEvidenceContext(text="bounded evidence", source_ids=source_ids, truncated=truncated)


def answer(*claims: list[str], limitations: list[str] | None = None) -> GroundedAnswer:
    return GroundedAnswer.model_validate(
        {
            "answer": "A structured answer.",
            "claims": [
                {"statement": f"Claim {index + 1}.", "source_ids": source_ids}
                for index, source_ids in enumerate(claims)
            ],
            "limitations": limitations or [],
        }
    )


def citations(*, valid: bool = True) -> CitationValidationResult:
    return CitationValidationResult(
        valid=valid,
        cited_source_ids=("ISSUE-1",),
        valid_source_ids=("ISSUE-1",) if valid else (),
        invalid_source_ids=() if valid else ("DOC-99",),
    )


class EvidenceSufficiencyTests(unittest.TestCase):
    def test_valid_citations_evidence_claims_and_no_limitations_are_sufficient(self) -> None:
        result = evidence_sufficiency.assess_evidence_sufficiency(
            answer(["ISSUE-1"], ["TEST-1"]), context("ISSUE-1", "TEST-1"), citations()
        )

        self.assertEqual(result.status, evidence_sufficiency.EvidenceSufficiencyStatus.SUFFICIENT)
        self.assertTrue(result.can_proceed)
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.limitations, ())

    def test_invalid_citations_have_highest_precedence(self) -> None:
        invalid = citations(valid=False)
        for formatted_context in (context(), context("ISSUE-1", truncated=True)):
            with self.subTest(context=formatted_context):
                result = evidence_sufficiency.assess_evidence_sufficiency(answer(["DOC-99"], limitations=["Limited."]), formatted_context, invalid)
                self.assertEqual(result.status, evidence_sufficiency.EvidenceSufficiencyStatus.INVALID_CITATIONS)
                self.assertFalse(result.can_proceed)
                self.assertEqual(result.limitations, ("Limited.",))
                self.assertEqual(result.reasons, ("One or more answer citations were not present in the supplied evidence context.",))

    def test_empty_context_has_precedence_over_zero_claims_and_limitations(self) -> None:
        result = evidence_sufficiency.assess_evidence_sufficiency(
            answer(limitations=["The deployment performer is not identified."]), context(), citations()
        )

        self.assertEqual(result.status, evidence_sufficiency.EvidenceSufficiencyStatus.INSUFFICIENT)
        self.assertFalse(result.can_proceed)
        self.assertEqual(result.reasons, ("No evidence sources were supplied for grounded project-specific claims.",))
        self.assertEqual(result.limitations, ("The deployment performer is not identified.",))

    def test_evidence_with_zero_claims_is_limited_but_can_proceed(self) -> None:
        result = evidence_sufficiency.assess_evidence_sufficiency(answer(), context("ISSUE-1"), citations())

        self.assertEqual(result.status, evidence_sufficiency.EvidenceSufficiencyStatus.LIMITED)
        self.assertTrue(result.can_proceed)
        self.assertEqual(result.reasons, ("The grounded answer contains no evidence-backed factual claims.",))

    def test_truncation_and_explicit_limitations_are_limited(self) -> None:
        truncated = evidence_sufficiency.assess_evidence_sufficiency(
            answer(["ISSUE-1"]), context("ISSUE-1", truncated=True), citations()
        )
        limited = evidence_sufficiency.assess_evidence_sufficiency(
            answer(["ISSUE-1"], limitations=["Testing evidence was not supplied."]), context("ISSUE-1"), citations()
        )

        self.assertEqual(truncated.status, evidence_sufficiency.EvidenceSufficiencyStatus.LIMITED)
        self.assertEqual(truncated.reasons, ("The supplied evidence context was truncated.",))
        self.assertEqual(limited.status, evidence_sufficiency.EvidenceSufficiencyStatus.LIMITED)
        self.assertEqual(limited.reasons, ("The grounded answer reports evidence limitations.",))

    def test_multiple_limited_conditions_have_fixed_reason_order_and_exact_limitations(self) -> None:
        limitations = ["Deployment performer is not identified.", "The document evidence is incomplete."]
        result = evidence_sufficiency.assess_evidence_sufficiency(
            answer(limitations=limitations), context("ISSUE-1", truncated=True), citations()
        )

        self.assertEqual(result.status, evidence_sufficiency.EvidenceSufficiencyStatus.LIMITED)
        self.assertTrue(result.can_proceed)
        self.assertEqual(
            result.reasons,
            (
                "The grounded answer contains no evidence-backed factual claims.",
                "The supplied evidence context was truncated.",
                "The grounded answer reports evidence limitations.",
            ),
        )
        self.assertEqual(result.limitations, tuple(limitations))

    def test_one_or_many_sources_do_not_trigger_count_heuristics(self) -> None:
        one_source = evidence_sufficiency.assess_evidence_sufficiency(answer(["ISSUE-1"]), context("ISSUE-1"), citations())
        many_sources = evidence_sufficiency.assess_evidence_sufficiency(
            answer(["ISSUE-1"]), context("ISSUE-1", "TEST-1", "DEPLOY-1", "COMMENT-1", "DOC-1"), citations()
        )

        self.assertEqual(one_source.status, evidence_sufficiency.EvidenceSufficiencyStatus.SUFFICIENT)
        self.assertEqual(many_sources.status, evidence_sufficiency.EvidenceSufficiencyStatus.SUFFICIENT)

    def test_inputs_are_not_mutated_result_is_frozen_and_calls_are_deterministic(self) -> None:
        grounded_answer = answer(["ISSUE-1"], limitations=["A limitation."])
        formatted_context = context("ISSUE-1", truncated=True)
        citation_result = citations()
        answer_before = copy.deepcopy(grounded_answer.model_dump())
        context_before = formatted_context
        citation_before = citation_result

        first = evidence_sufficiency.assess_evidence_sufficiency(grounded_answer, formatted_context, citation_result)
        second = evidence_sufficiency.assess_evidence_sufficiency(grounded_answer, formatted_context, citation_result)

        self.assertEqual(first, second)
        self.assertEqual(grounded_answer.model_dump(), answer_before)
        self.assertEqual(formatted_context, context_before)
        self.assertEqual(citation_result, citation_before)
        with self.assertRaises(FrozenInstanceError):
            first.status = evidence_sufficiency.EvidenceSufficiencyStatus.SUFFICIENT  # type: ignore[misc]

    def test_module_is_provider_neutral_and_has_no_external_service_dependencies(self) -> None:
        self.assertEqual(
            evidence_sufficiency.EvidenceSufficiencyResult.__dataclass_fields__.keys(),
            {"status", "can_proceed", "reasons", "limitations"},
        )
        for forbidden_name in (
            "LLMService", "GroqProvider", "GeminiProvider", "Session", "engine",
            "format_evidence_context", "build_grounding_system_prompt", "validate_answer_citations",
            "build_evidence_context", "search_project_documents", "embed_query", "requests", "httpx",
        ):
            self.assertFalse(hasattr(evidence_sufficiency, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
