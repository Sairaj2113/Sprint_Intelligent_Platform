from __future__ import annotations

import unittest

from app.models import DocumentType
from app.services.query_intent_service import (
    QueryIntent,
    QueryIntentError,
    classify_query_intent,
)


class QueryIntentServiceTests(unittest.TestCase):
    def test_structured_query_extracts_employee_and_sprint_scope(self) -> None:
        result = classify_query_intent("What did Sairaj contribute in Sprint 2?")

        self.assertEqual(result.intent, QueryIntent.STRUCTURED)
        self.assertTrue(result.needs_structured_evidence)
        self.assertFalse(result.needs_document_evidence)
        self.assertEqual(result.employee_reference, "Sairaj")
        self.assertEqual(result.sprint_reference, "Sprint 2")

    def test_document_queries_and_explicit_document_type_hints(self) -> None:
        requirements = classify_query_intent("What are the model approval requirements?")
        self.assertEqual(requirements.intent, QueryIntent.DOCUMENT)
        self.assertEqual(requirements.document_types, [])

        prd = classify_query_intent("What does the PRD require for model approval?")
        self.assertEqual(prd.intent, QueryIntent.DOCUMENT)
        self.assertEqual(prd.document_types, [DocumentType.PRD])

        trd = classify_query_intent("What does the TRD specify for the scoring API?")
        self.assertEqual(trd.intent, QueryIntent.DOCUMENT)
        self.assertEqual(trd.document_types, [DocumentType.TRD])

        architecture = classify_query_intent("Explain the architecture requirements")
        self.assertEqual(architecture.intent, QueryIntent.DOCUMENT)
        self.assertEqual(architecture.document_types, [DocumentType.ARCHITECTURE])

    def test_hybrid_queries_combine_explicit_structured_and_document_signals(self) -> None:
        contribution = classify_query_intent(
            "What did Sairaj contribute toward the model requirements?"
        )
        self.assertEqual(contribution.intent, QueryIntent.HYBRID)
        self.assertTrue(contribution.needs_structured_evidence)
        self.assertTrue(contribution.needs_document_evidence)
        self.assertEqual(contribution.employee_reference, "Sairaj")

        tested = classify_query_intent(
            "Was Sairaj's Sprint 3 work tested and aligned with the PRD requirements?"
        )
        self.assertEqual(tested.intent, QueryIntent.HYBRID)
        self.assertEqual(tested.employee_reference, "Sairaj")
        self.assertEqual(tested.sprint_reference, "Sprint 3")
        self.assertEqual(tested.document_types, [DocumentType.PRD])

    def test_employee_feature_and_system_queries_preserve_full_reference_and_use_hybrid_evidence(self) -> None:
        feature = classify_query_intent("What features did Sairaj Pankar work on?")
        capability = classify_query_intent("What capabilities did Sairaj contribute to?")
        implementation = classify_query_intent("What did Sairaj implement in the project?")

        self.assertEqual(feature.intent, QueryIntent.HYBRID)
        self.assertEqual(feature.employee_reference, "Sairaj Pankar")
        self.assertTrue(feature.needs_structured_evidence)
        self.assertTrue(feature.needs_document_evidence)
        self.assertEqual(capability.intent, QueryIntent.HYBRID)
        self.assertEqual(capability.employee_reference, "Sairaj")
        self.assertEqual(implementation.intent, QueryIntent.HYBRID)
        self.assertEqual(implementation.employee_reference, "Sairaj")

    def test_employee_assignment_and_code_queries_remain_structured(self) -> None:
        assigned = classify_query_intent("What issues were assigned to Sairaj?")
        employee_code = classify_query_intent("What did EMP001 contribute?")

        self.assertEqual(assigned.intent, QueryIntent.STRUCTURED)
        self.assertEqual(assigned.employee_reference, "Sairaj")
        self.assertEqual(employee_code.intent, QueryIntent.STRUCTURED)
        self.assertEqual(employee_code.employee_reference, "EMP001")

    def test_remaining_structured_unknown_and_case_insensitive_queries(self) -> None:
        completed = classify_query_intent("How many issues were completed?")
        self.assertEqual(completed.intent, QueryIntent.STRUCTURED)

        deployment = classify_query_intent("What is the deployment status?")
        self.assertEqual(deployment.intent, QueryIntent.STRUCTURED)

        unknown = classify_query_intent("Please explain this to me")
        self.assertEqual(unknown.intent, QueryIntent.HYBRID)
        self.assertIn("default_hybrid", unknown.matched_signals)

        case_insensitive = classify_query_intent("WHAT DOES THE prd REQUIRE?")
        self.assertEqual(case_insensitive.intent, QueryIntent.DOCUMENT)
        self.assertEqual(case_insensitive.document_types, [DocumentType.PRD])

    def test_blank_query_raises_controlled_error(self) -> None:
        with self.assertRaises(QueryIntentError):
            classify_query_intent(" \t\n")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
