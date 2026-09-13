from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.evaluation.retrieval_evaluation import (
    RetrievalBenchmarkCase,
    RetrievalEvaluationError,
    evaluate_case_results,
    evaluate_retrieval_cases,
    summarize_evaluation,
)
from app.models import DocumentType
from app.services.retrieval_service import SemanticRetrievalResult


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def result(
    *,
    page_number: int | None = 1,
    chunk_index: int = 0,
    document_type: DocumentType = DocumentType.PRD,
    distance: float = 0.2,
) -> SemanticRetrievalResult:
    return SemanticRetrievalResult(
        document_id=DOCUMENT_ID,
        chunk_id=uuid.uuid4(),
        chunk_index=chunk_index,
        document_title="BLI PRD",
        document_type=document_type,
        content="deterministic evidence",
        page_number=page_number,
        section_title="Requirements",
        metadata_json={"source_type": "pdf"},
        distance=distance,
    )


def case(**kwargs: object) -> RetrievalBenchmarkCase:
    defaults: dict[str, object] = {
        "id": "CASE-01",
        "project_key": "BLI",
        "query": "quality requirements",
        "expected_page_numbers": [8],
    }
    defaults.update(kwargs)
    return RetrievalBenchmarkCase(**defaults)  # type: ignore[arg-type]


class RetrievalEvaluationTests(unittest.TestCase):
    def test_relevant_result_at_rank_one_sets_all_hit_metrics(self) -> None:
        evaluation = evaluate_case_results(case(), [result(page_number=8, distance=0.11)])

        self.assertEqual(evaluation.first_relevant_rank, 1)
        self.assertEqual(evaluation.best_relevant_distance, 0.11)
        self.assertTrue(evaluation.hit_at_1)
        self.assertTrue(evaluation.hit_at_3)
        self.assertTrue(evaluation.hit_at_5)

    def test_relevant_result_at_rank_two_has_hit_at_3_and_hit_at_5_only(self) -> None:
        evaluation = evaluate_case_results(
            case(), [result(page_number=1), result(page_number=8, distance=0.35)]
        )

        self.assertEqual(evaluation.first_relevant_rank, 2)
        self.assertFalse(evaluation.hit_at_1)
        self.assertTrue(evaluation.hit_at_3)
        self.assertTrue(evaluation.hit_at_5)

    def test_relevant_result_at_rank_five_and_no_relevant_result(self) -> None:
        rank_five = evaluate_case_results(
            case(),
            [result(page_number=index) for index in (1, 2, 3, 4, 8)],
        )
        self.assertEqual(rank_five.first_relevant_rank, 5)
        self.assertFalse(rank_five.hit_at_1)
        self.assertFalse(rank_five.hit_at_3)
        self.assertTrue(rank_five.hit_at_5)

        no_match = evaluate_case_results(case(), [result(page_number=1)])
        self.assertIsNone(no_match.first_relevant_rank)
        self.assertIsNone(no_match.best_relevant_distance)
        self.assertFalse(no_match.hit_at_1)
        self.assertFalse(no_match.hit_at_3)
        self.assertFalse(no_match.hit_at_5)

    def test_page_chunk_and_document_type_matching_are_deterministic(self) -> None:
        page_match = evaluate_case_results(case(expected_page_numbers=[6]), [result(page_number=6)])
        self.assertEqual(page_match.first_relevant_rank, 1)

        chunk_match = evaluate_case_results(
            case(expected_page_numbers=None, expected_chunk_indexes=[4]),
            [result(page_number=1, chunk_index=4)],
        )
        self.assertEqual(chunk_match.first_relevant_rank, 1)

        restricted = case(expected_page_numbers=[8], expected_document_types=[DocumentType.TRD])
        wrong_type = evaluate_case_results(restricted, [result(page_number=8)])
        right_type = evaluate_case_results(
            restricted, [result(page_number=8, document_type=DocumentType.TRD)]
        )
        self.assertIsNone(wrong_type.first_relevant_rank)
        self.assertEqual(right_type.first_relevant_rank, 1)

    def test_summary_calculates_hit_counts_rates_and_mrr_with_zero_relevant_cases(self) -> None:
        rank_one = evaluate_case_results(case(id="CASE-01"), [result(page_number=8)])
        rank_two = evaluate_case_results(
            case(id="CASE-02"), [result(page_number=1), result(page_number=8)]
        )
        no_match = evaluate_case_results(case(id="CASE-03"), [result(page_number=1)])
        summary = summarize_evaluation([rank_one, rank_two, no_match])

        self.assertEqual(summary.total_cases, 3)
        self.assertEqual(summary.hit_at_1_count, 1)
        self.assertEqual(summary.hit_at_3_count, 2)
        self.assertEqual(summary.hit_at_5_count, 2)
        self.assertAlmostEqual(summary.hit_at_1_rate, 1 / 3)
        self.assertAlmostEqual(summary.hit_at_3_rate, 2 / 3)
        self.assertAlmostEqual(summary.hit_at_5_rate, 2 / 3)
        self.assertAlmostEqual(summary.mean_reciprocal_rank, 0.5)

        empty_summary = summarize_evaluation([])
        self.assertEqual(empty_summary.total_cases, 0)
        self.assertEqual(empty_summary.hit_at_1_rate, 0.0)
        self.assertEqual(empty_summary.mean_reciprocal_rank, 0.0)

    def test_benchmark_case_requires_page_or_chunk_evidence(self) -> None:
        with self.assertRaises(ValueError):
            RetrievalBenchmarkCase("CASE-INVALID", "BLI", "query")

    def test_evaluator_resolves_project_and_reuses_existing_retrieval_service(self) -> None:
        db = Mock()
        db.scalar.return_value = SimpleNamespace(id=PROJECT_ID)
        benchmark_case = case()
        with patch(
            "app.evaluation.retrieval_evaluation.search_project_documents",
            return_value=[result(page_number=8)],
        ) as search:
            summary = evaluate_retrieval_cases(db, [benchmark_case], top_k=5)

        search.assert_called_once_with(
            db=db,
            project_id=PROJECT_ID,
            query=benchmark_case.query,
            top_k=5,
        )
        self.assertEqual(summary.hit_at_1_count, 1)

    def test_missing_project_and_retrieval_failure_are_controlled(self) -> None:
        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(RetrievalEvaluationError):
            evaluate_retrieval_cases(missing_project_db, [case()])

        failing_db = Mock()
        failing_db.scalar.return_value = SimpleNamespace(id=PROJECT_ID)
        with patch(
            "app.evaluation.retrieval_evaluation.search_project_documents",
            side_effect=RuntimeError("synthetic retrieval failure"),
        ):
            with self.assertRaises(RetrievalEvaluationError) as error:
                evaluate_retrieval_cases(failing_db, [case()])
        self.assertIsInstance(error.exception.__cause__, RuntimeError)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
