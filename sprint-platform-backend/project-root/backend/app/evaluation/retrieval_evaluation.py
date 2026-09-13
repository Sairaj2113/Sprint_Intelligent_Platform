"""Deterministic evaluation of semantic retrieval against known evidence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DocumentType, Project
from app.services.retrieval_service import SemanticRetrievalResult, search_project_documents


class RetrievalEvaluationError(Exception):
    """Controlled error raised when a benchmark cannot be evaluated."""


@dataclass(frozen=True)
class RetrievalBenchmarkCase:
    id: str
    project_key: str
    query: str
    expected_page_numbers: list[int] | None = None
    expected_chunk_indexes: list[int] | None = None
    expected_document_types: list[DocumentType] | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.expected_page_numbers and not self.expected_chunk_indexes:
            raise ValueError("A benchmark case requires at least one expected target")


@dataclass(frozen=True)
class RetrievalEvaluationCaseResult:
    case_id: str
    query: str
    returned_results: list[SemanticRetrievalResult]
    expected_page_numbers: list[int] | None
    expected_chunk_indexes: list[int] | None
    expected_document_types: list[DocumentType] | None
    hit_at_1: bool
    hit_at_3: bool
    hit_at_5: bool
    first_relevant_rank: int | None
    best_relevant_distance: float | None


@dataclass(frozen=True)
class RetrievalEvaluationSummary:
    total_cases: int
    hit_at_1_count: int
    hit_at_3_count: int
    hit_at_5_count: int
    hit_at_1_rate: float
    hit_at_3_rate: float
    hit_at_5_rate: float
    mean_reciprocal_rank: float
    cases: list[RetrievalEvaluationCaseResult]


def is_relevant_result(
    result: SemanticRetrievalResult, case: RetrievalBenchmarkCase
) -> bool:
    """Match a result to explicit page/chunk evidence and optional document type."""
    page_match = (
        case.expected_page_numbers is not None
        and result.page_number in case.expected_page_numbers
    )
    chunk_match = (
        case.expected_chunk_indexes is not None
        and result.chunk_index in case.expected_chunk_indexes
    )
    type_match = (
        case.expected_document_types is None
        or result.document_type in case.expected_document_types
    )
    return (page_match or chunk_match) and type_match


def evaluate_case_results(
    case: RetrievalBenchmarkCase,
    returned_results: list[SemanticRetrievalResult],
) -> RetrievalEvaluationCaseResult:
    """Calculate deterministic ranks and hit metrics for one benchmark case."""
    relevant_results = [
        (rank, result)
        for rank, result in enumerate(returned_results, start=1)
        if is_relevant_result(result, case)
    ]
    first_relevant_rank = relevant_results[0][0] if relevant_results else None
    best_relevant_distance = (
        min(result.distance for _, result in relevant_results)
        if relevant_results
        else None
    )

    return RetrievalEvaluationCaseResult(
        case_id=case.id,
        query=case.query,
        returned_results=returned_results,
        expected_page_numbers=case.expected_page_numbers,
        expected_chunk_indexes=case.expected_chunk_indexes,
        expected_document_types=case.expected_document_types,
        hit_at_1=first_relevant_rank is not None and first_relevant_rank <= 1,
        hit_at_3=first_relevant_rank is not None and first_relevant_rank <= 3,
        hit_at_5=first_relevant_rank is not None and first_relevant_rank <= 5,
        first_relevant_rank=first_relevant_rank,
        best_relevant_distance=best_relevant_distance,
    )


def summarize_evaluation(
    case_results: list[RetrievalEvaluationCaseResult],
) -> RetrievalEvaluationSummary:
    """Aggregate hit rates and MRR, treating missing relevant results as zero."""
    total_cases = len(case_results)
    hit_at_1_count = sum(result.hit_at_1 for result in case_results)
    hit_at_3_count = sum(result.hit_at_3 for result in case_results)
    hit_at_5_count = sum(result.hit_at_5 for result in case_results)
    reciprocal_rank_total = sum(
        1 / result.first_relevant_rank
        for result in case_results
        if result.first_relevant_rank is not None
    )
    denominator = total_cases or 1
    return RetrievalEvaluationSummary(
        total_cases=total_cases,
        hit_at_1_count=hit_at_1_count,
        hit_at_3_count=hit_at_3_count,
        hit_at_5_count=hit_at_5_count,
        hit_at_1_rate=hit_at_1_count / denominator,
        hit_at_3_rate=hit_at_3_count / denominator,
        hit_at_5_rate=hit_at_5_count / denominator,
        mean_reciprocal_rank=reciprocal_rank_total / denominator,
        cases=case_results,
    )


def evaluate_retrieval_cases(
    db: Session,
    cases: list[RetrievalBenchmarkCase],
    top_k: int = 5,
) -> RetrievalEvaluationSummary:
    """Run a benchmark through the existing retrieval service without duplicating search."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    case_results: list[RetrievalEvaluationCaseResult] = []
    for case in cases:
        project = db.scalar(select(Project).where(Project.project_key == case.project_key))
        if project is None:
            raise RetrievalEvaluationError(f"Project not found for benchmark case {case.id}")
        try:
            returned_results = search_project_documents(
                db=db,
                project_id=project.id,
                query=case.query,
                top_k=top_k,
            )
        except Exception as error:
            raise RetrievalEvaluationError(
                f"Unable to retrieve results for benchmark case {case.id}"
            ) from error
        case_results.append(evaluate_case_results(case, returned_results))

    return summarize_evaluation(case_results)
