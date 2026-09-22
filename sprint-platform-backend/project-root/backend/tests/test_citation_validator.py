"""Pure deterministic tests for Phase 10E citation membership validation."""

from __future__ import annotations

import copy
import unittest
from dataclasses import FrozenInstanceError

import app.services.llm.citation_validator as citation_validator
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


class CitationValidatorTests(unittest.TestCase):
    def test_all_citations_valid_and_unused_context_evidence_is_allowed(self) -> None:
        result = citation_validator.validate_answer_citations(
            answer(["ISSUE-4", "TEST-3"]), context("ISSUE-4", "TEST-3", "DOC-2")
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.cited_source_ids, ("ISSUE-4", "TEST-3"))
        self.assertEqual(result.valid_source_ids, ("ISSUE-4", "TEST-3"))
        self.assertEqual(result.invalid_source_ids, ())

    def test_one_and_multiple_unknown_citations_return_detailed_failure(self) -> None:
        one_invalid = citation_validator.validate_answer_citations(
            answer(["ISSUE-4", "DOC-99"]), context("ISSUE-4")
        )
        multiple_invalid = citation_validator.validate_answer_citations(
            answer(["DOC-99", "ISSUE-4"], ["COMMENT-8", "TEST-3"]), context("TEST-3", "ISSUE-4")
        )

        self.assertFalse(one_invalid.valid)
        self.assertEqual(one_invalid.valid_source_ids, ("ISSUE-4",))
        self.assertEqual(one_invalid.invalid_source_ids, ("DOC-99",))
        self.assertEqual(multiple_invalid.cited_source_ids, ("DOC-99", "ISSUE-4", "COMMENT-8", "TEST-3"))
        self.assertEqual(multiple_invalid.valid_source_ids, ("ISSUE-4", "TEST-3"))
        self.assertEqual(multiple_invalid.invalid_source_ids, ("DOC-99", "COMMENT-8"))

    def test_cross_claim_reuse_is_deduplicated_at_first_occurrence_only(self) -> None:
        result = citation_validator.validate_answer_citations(
            answer(["ISSUE-4", "TEST-3"], ["DOC-2", "ISSUE-4"]),
            context("DOC-2", "ISSUE-4", "TEST-3"),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.cited_source_ids, ("ISSUE-4", "TEST-3", "DOC-2"))
        self.assertEqual(result.valid_source_ids, ("ISSUE-4", "TEST-3", "DOC-2"))

    def test_context_order_never_reorders_citation_or_partition_order(self) -> None:
        result = citation_validator.validate_answer_citations(
            answer(["DOC-9", "ISSUE-2"], ["DOC-99", "TEST-1"]),
            context("ISSUE-2", "TEST-1", "DOC-9"),
        )

        self.assertEqual(result.cited_source_ids, ("DOC-9", "ISSUE-2", "DOC-99", "TEST-1"))
        self.assertEqual(result.valid_source_ids, ("DOC-9", "ISSUE-2", "TEST-1"))
        self.assertEqual(result.invalid_source_ids, ("DOC-99",))

    def test_zero_claims_are_valid_with_or_without_limitations_and_empty_context(self) -> None:
        empty_context = context()
        without_limitations = citation_validator.validate_answer_citations(answer(), empty_context)
        with_limitations = citation_validator.validate_answer_citations(
            answer(limitations=["Evidence is incomplete."]), empty_context
        )

        for result in (without_limitations, with_limitations):
            self.assertTrue(result.valid)
            self.assertEqual(result.cited_source_ids, ())
            self.assertEqual(result.valid_source_ids, ())
            self.assertEqual(result.invalid_source_ids, ())

    def test_empty_context_cited_claim_and_outside_context_source_are_invalid(self) -> None:
        empty = citation_validator.validate_answer_citations(answer(["ISSUE-1"]), context())
        outside = citation_validator.validate_answer_citations(
            answer(["ISSUE-50"]), context("ISSUE-1", "ISSUE-2")
        )

        self.assertFalse(empty.valid)
        self.assertEqual(empty.invalid_source_ids, ("ISSUE-1",))
        self.assertFalse(outside.valid)
        self.assertEqual(outside.invalid_source_ids, ("ISSUE-50",))

    def test_truncated_context_uses_the_same_exact_membership_rule(self) -> None:
        valid = citation_validator.validate_answer_citations(answer(["ISSUE-1"]), context("ISSUE-1", truncated=True))
        omitted = citation_validator.validate_answer_citations(answer(["ISSUE-3"]), context("ISSUE-1", "ISSUE-2", truncated=True))

        self.assertTrue(valid.valid)
        self.assertFalse(omitted.valid)
        self.assertEqual(omitted.invalid_source_ids, ("ISSUE-3",))

    def test_inputs_are_not_mutated_results_are_frozen_and_calls_are_deterministic(self) -> None:
        grounded_answer = answer(["ISSUE-4"], ["DOC-2", "ISSUE-4"])
        formatted_context = context("ISSUE-4", "DOC-2")
        answer_before = copy.deepcopy(grounded_answer.model_dump())
        context_before = formatted_context

        first = citation_validator.validate_answer_citations(grounded_answer, formatted_context)
        second = citation_validator.validate_answer_citations(grounded_answer, formatted_context)

        self.assertEqual(first, second)
        self.assertEqual(grounded_answer.model_dump(), answer_before)
        self.assertEqual(formatted_context, context_before)
        with self.assertRaises(FrozenInstanceError):
            first.valid = False  # type: ignore[misc]

    def test_module_is_provider_neutral_and_has_no_external_service_dependencies(self) -> None:
        self.assertEqual(
            citation_validator.CitationValidationResult.__dataclass_fields__.keys(),
            {"valid", "cited_source_ids", "valid_source_ids", "invalid_source_ids"},
        )
        for forbidden_name in (
            "LLMService", "GroqProvider", "GeminiProvider", "Session", "engine",
            "format_evidence_context", "build_grounding_system_prompt", "build_evidence_context",
            "search_project_documents", "embed_query", "requests", "httpx",
        ):
            self.assertFalse(hasattr(citation_validator, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
