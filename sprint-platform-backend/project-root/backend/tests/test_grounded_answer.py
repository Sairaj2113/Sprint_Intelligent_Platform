"""Strict, no-network tests for the Phase 10D grounded-answer contract."""

from __future__ import annotations

import unittest

import app.services.llm.grounded_answer as grounded_answer
from pydantic import ValidationError


GroundedAnswer = grounded_answer.GroundedAnswer
GroundedClaim = grounded_answer.GroundedClaim


def valid_payload() -> dict[str, object]:
    return {
        "answer": "BLI-15 is recorded as completed.",
        "claims": [
            {"statement": "BLI-15 is recorded as completed.", "source_ids": ["ISSUE-4"]}
        ],
        "limitations": [],
    }


class GroundedAnswerTests(unittest.TestCase):
    def test_valid_one_and_multiple_claim_answers_preserve_source_order(self) -> None:
        one = GroundedAnswer.model_validate(valid_payload())
        multiple = GroundedAnswer.model_validate(
            {
                "answer": "The project has documented issue and test evidence.",
                "claims": [
                    {"statement": "An issue is recorded as completed.", "source_ids": ["ISSUE-4", "TEST-3"]},
                    {"statement": "A deployment is recorded.", "source_ids": ["DEPLOY-9"]},
                ],
                "limitations": ["Document evidence was not supplied.", "The context is truncated."],
            }
        )

        self.assertEqual(one.claims[0].source_ids, ["ISSUE-4"])
        self.assertEqual(multiple.claims[0].source_ids, ["ISSUE-4", "TEST-3"])
        self.assertEqual(multiple.limitations, ["Document evidence was not supplied.", "The context is truncated."])

    def test_zero_claim_payloads_are_structurally_valid(self) -> None:
        with_limitations = GroundedAnswer.model_validate(
            {"answer": "The supplied evidence does not establish a factual claim.", "claims": [], "limitations": ["No matching evidence was supplied."]}
        )
        empty = GroundedAnswer.model_validate(
            {"answer": "No factual claim is provided.", "claims": [], "limitations": []}
        )

        self.assertEqual(with_limitations.claims, [])
        self.assertEqual(empty.limitations, [])

    def test_blank_answer_claim_statement_source_id_and_limitation_are_rejected(self) -> None:
        invalid_payloads = (
            {"answer": "  ", "claims": [], "limitations": []},
            {"answer": "answer", "claims": [{"statement": "\t", "source_ids": ["ISSUE-1"]}], "limitations": []},
            {"answer": "answer", "claims": [{"statement": "claim", "source_ids": [" "]}], "limitations": []},
            {"answer": "answer", "claims": [], "limitations": ["\n"]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GroundedAnswer.model_validate(payload)

    def test_empty_and_duplicate_source_ids_are_rejected_without_rewriting(self) -> None:
        empty = {"statement": "claim", "source_ids": []}
        duplicate = {"statement": "claim", "source_ids": ["ISSUE-1", "ISSUE-1"]}

        for payload in (empty, duplicate):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GroundedClaim.model_validate(payload)

    def test_every_allowed_source_prefix_and_positive_number_are_accepted(self) -> None:
        source_ids = ["ISSUE-1", "TEST-3", "DEPLOY-9", "COMMENT-2", "DOC-15", "ISSUE-42"]
        claim = GroundedClaim.model_validate({"statement": "Recorded evidence exists.", "source_ids": source_ids})

        self.assertEqual(claim.source_ids, source_ids)

    def test_invalid_source_prefix_number_and_leading_zero_are_rejected(self) -> None:
        invalid_source_ids = ("SOURCE-1", "issue-1", "ISSUE-0", "DOC-0", "DOC--1", "DOC-01", "DOC-1.5")
        for source_id in invalid_source_ids:
            with self.subTest(source_id=source_id), self.assertRaises(ValidationError):
                GroundedClaim.model_validate({"statement": "claim", "source_ids": [source_id]})

    def test_duplicate_limitations_are_rejected_and_order_is_not_changed(self) -> None:
        with self.assertRaises(ValidationError):
            GroundedAnswer.model_validate(
                {"answer": "answer", "claims": [], "limitations": ["Missing evidence.", "Missing evidence."]}
            )
        answer = GroundedAnswer.model_validate(
            {"answer": "answer", "claims": [], "limitations": ["First limitation.", "Second limitation."]}
        )
        self.assertEqual(answer.limitations, ["First limitation.", "Second limitation."])

    def test_unknown_fields_and_malformed_types_are_rejected(self) -> None:
        extra_top_level = {**valid_payload(), "provider": "unexpected"}
        extra_claim = {
            "answer": "answer",
            "claims": [{"statement": "claim", "source_ids": ["ISSUE-1"], "model": "unexpected"}],
            "limitations": [],
        }
        malformed = (
            {"answer": 1, "claims": [], "limitations": []},
            {"answer": "answer", "claims": "not-a-list", "limitations": []},
            {"answer": "answer", "claims": [{"statement": "claim", "source_ids": "ISSUE-1"}], "limitations": []},
            {"answer": "answer", "claims": [], "limitations": [1]},
        )
        for payload in (extra_top_level, extra_claim, *malformed):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                GroundedAnswer.model_validate(payload)

    def test_serialization_schema_and_provider_fields_are_stable_and_neutral(self) -> None:
        answer = GroundedAnswer.model_validate(valid_payload())
        self.assertEqual(answer.model_dump(), valid_payload())
        schema = GroundedAnswer.model_json_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["properties"]), {"answer", "claims", "limitations"})
        for forbidden_field in ("provider", "model", "usage", "token_usage", "fallback_used", "groq", "gemini", "gpt_oss"):
            self.assertNotIn(forbidden_field, schema["properties"])

    def test_module_has_no_external_service_dependencies(self) -> None:
        for forbidden_name in (
            "LLMService", "GroqProvider", "GeminiProvider", "LLMGenerationRequest",
            "format_evidence_context", "build_grounding_system_prompt", "build_evidence_context",
            "search_project_documents", "embed_query", "Session", "requests", "httpx",
        ):
            self.assertFalse(hasattr(grounded_answer, forbidden_name), forbidden_name)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
