"""Run the BLI retrieval benchmark against the configured database."""

from __future__ import annotations

from app.database import SessionLocal
from app.evaluation.benchmarks.bli_retrieval_cases import BLI_RETRIEVAL_CASES
from app.evaluation.retrieval_evaluation import evaluate_retrieval_cases


def main() -> None:
    """Evaluate BLI retrieval and print a compact, readable terminal report."""
    db = SessionLocal()
    try:
        summary = evaluate_retrieval_cases(db, BLI_RETRIEVAL_CASES)
    finally:
        db.close()

    print("Retrieval Evaluation - BLI")
    print()
    print(f"Total cases: {summary.total_cases}")
    print(f"Hit@1: {summary.hit_at_1_count}/{summary.total_cases} = {summary.hit_at_1_rate:.2f}")
    print(f"Hit@3: {summary.hit_at_3_count}/{summary.total_cases} = {summary.hit_at_3_rate:.2f}")
    print(f"Hit@5: {summary.hit_at_5_count}/{summary.total_cases} = {summary.hit_at_5_rate:.2f}")
    print(f"MRR: {summary.mean_reciprocal_rank:.2f}")
    print("\nPer-case:")
    for case in summary.cases:
        print(case.case_id)
        print(f"Query: {case.query}")
        print(f"First relevant rank: {case.first_relevant_rank}")
        print(f"Hit@1: {str(case.hit_at_1).lower()}")
        print(f"Hit@3: {str(case.hit_at_3).lower()}")
        print(f"Hit@5: {str(case.hit_at_5).lower()}")


if __name__ == "__main__":
    main()
