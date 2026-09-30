"""No-network tests for deterministic grounded-analysis input budgeting."""

from __future__ import annotations

import unittest
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

from app.services.evidence_context_service import (
    BoundedEvidenceContext,
    EvidenceCategoryCoverage,
    EvidenceContextStats,
    EvidenceCoverage,
    INPUT_BUDGET_TRUNCATION_WARNING,
)
from app.services.evidence_source_service import EvidenceSource, EvidenceSourceType
from app.services.llm.citation_validator import validate_answer_citations
from app.services.llm.evidence_context_formatter import format_evidence_context
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.llm.input_budget_service import (
    GroundedInputBudget,
    GroundedInputBudgetError,
    estimate_input_tokens,
    trim_context_to_input_budget,
)
from app.services.query_intent_service import QueryIntent


def _issue(index: int, *, size: int = 5_000) -> SimpleNamespace:
    return SimpleNamespace(
        id=UUID(int=index), issue_key=f"BLI-{index}", title=f"Issue {index}",
        issue_type="TASK", status="TODO", story_points=None, assignee_id=None,
        assignee_name=None, sprint_id=None, sprint_name=None,
        description="d" * size, acceptance_criteria=None, technical_notes=None,
        parent_issue_key=None, parent_issue_title=None, created_at=None, completed_at=None,
    )


def _source(item: SimpleNamespace, index: int) -> EvidenceSource:
    return EvidenceSource(
        source_id=f"ISSUE-{index}", source_type=EvidenceSourceType.ISSUE,
        project_key="BLI", record_id=item.id, title=f"{item.issue_key}: {item.title}",
        issue_key=item.issue_key, document_id=None, chunk_id=None, chunk_index=None,
        document_type=None, page_number=None, section_title=None, metadata={},
    )


def _context(*, size: int = 5_000, requires_complete: bool = False) -> BoundedEvidenceContext:
    issues = [_issue(index, size=size) for index in range(1, 4)]
    return BoundedEvidenceContext(
        query="Which requirements have supporting work?", project_key="BLI",
        intent=QueryIntent.STRUCTURED, employee_reference=None, sprint_reference=None,
        issues=issues, tests=[], deployments=[], comments=[], documents=[],
        sources=[_source(item, index) for index, item in enumerate(issues, start=1)],
        stats=EvidenceContextStats(
            available_issues=3, included_issues=3, omitted_issues=0,
            available_tests=0, included_tests=0, omitted_tests=0,
            available_deployments=0, included_deployments=0, omitted_deployments=0,
            available_comments=0, included_comments=0, omitted_comments=0,
            available_documents=0, included_documents=0, omitted_documents=0,
            available_sources=3, included_sources=3, truncated=False,
        ),
        warnings=[],
        coverage=EvidenceCoverage(
            selected_scope="PROJECT",
            issues=EvidenceCategoryCoverage(True, 3, 3, 0, True),
            tests=EvidenceCategoryCoverage(True, 0, 0, 0, True),
            deployments=EvidenceCategoryCoverage(True, 0, 0, 0, True),
            comments=EvidenceCategoryCoverage(True, 0, 0, 0, True),
            documents=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        ),
        requires_complete_evidence=requires_complete,
        required_evidence_categories=("issues",) if requires_complete else (),
    )


def _measure(context: BoundedEvidenceContext) -> int:
    formatted = format_evidence_context(context)
    return estimate_input_tokens("grounding policy", formatted.text)


class GroundedInputBudgetTests(unittest.TestCase):
    def test_calibrated_estimator_is_conservative_against_measured_groq_request(self) -> None:
        # 3.5 bytes/token was selected from the observed 30,496-byte / 7,627
        # token request.  The 1,024-byte envelope headroom makes the estimate
        # 9,006, safely above the reported input-token count.
        estimate = estimate_input_tokens("s" * 3_269, "u" * 27_227)
        self.assertEqual(estimate, 9_006)
        self.assertGreater(estimate, 7_627)

    def test_trim_is_deterministic_preserves_prefix_order_and_rebuilds_source_registry(self) -> None:
        context = _context()
        budget = GroundedInputBudget(effective_envelope_tokens=5_000, safety_margin_tokens=1_000)

        first = trim_context_to_input_budget(context, budget=budget, measure_context=_measure)
        second = trim_context_to_input_budget(context, budget=budget, measure_context=_measure)

        self.assertEqual([issue.id for issue in first.issues], [issue.id for issue in second.issues])
        self.assertEqual([issue.id for issue in first.issues], [issue.id for issue in context.issues[:len(first.issues)]])
        self.assertEqual([source.source_id for source in first.sources], [f"ISSUE-{index}" for index in range(1, len(first.issues) + 1)])
        self.assertLessEqual(_measure(first), budget.max_estimated_input_tokens)
        self.assertTrue(first.stats.truncated)
        self.assertIn(INPUT_BUDGET_TRUNCATION_WARNING, first.warnings)
        self.assertEqual(context.stats.included_issues, 3)

    def test_budgeted_context_keeps_only_supplied_ids_for_unchanged_citation_validation(self) -> None:
        budgeted = trim_context_to_input_budget(
            _context(),
            budget=GroundedInputBudget(effective_envelope_tokens=5_000, safety_margin_tokens=1_000),
            measure_context=_measure,
        )
        formatted = format_evidence_context(budgeted)
        removed_id = f"ISSUE-{len(budgeted.issues) + 1}"
        answer = GroundedAnswer.model_validate({
            "answer": "A claim.",
            "claims": [{"statement": "A claim.", "source_ids": [removed_id]}],
            "limitations": [],
        })

        validation = validate_answer_citations(answer, formatted)
        self.assertFalse(validation.valid)
        self.assertEqual(validation.invalid_source_ids, (removed_id,))

    def test_budget_truncation_recomputes_required_category_coverage_warning(self) -> None:
        budgeted = trim_context_to_input_budget(
            _context(requires_complete=True),
            budget=GroundedInputBudget(effective_envelope_tokens=5_000, safety_margin_tokens=1_000),
            measure_context=_measure,
        )

        self.assertFalse(budgeted.coverage.issues.complete)
        self.assertIn(
            f"Aggregate or absence claims about issues are limited because {budgeted.stats.omitted_issues} of 3 issue records were omitted by the grounded-analysis input budget.",
            budgeted.warnings,
        )

    def test_oversized_request_without_removable_evidence_is_controlled(self) -> None:
        original = _context(size=1)
        empty_stats = EvidenceContextStats(
            available_issues=0, included_issues=0, omitted_issues=0,
            available_tests=0, included_tests=0, omitted_tests=0,
            available_deployments=0, included_deployments=0, omitted_deployments=0,
            available_comments=0, included_comments=0, omitted_comments=0,
            available_documents=0, included_documents=0, omitted_documents=0,
            available_sources=0, included_sources=0, truncated=False,
        )
        empty = replace(
            original,
            issues=[],
            sources=[],
            stats=empty_stats,
            coverage=replace(
                original.coverage,
                issues=EvidenceCategoryCoverage(True, 0, 0, 0, True),
            ),
        )
        with self.assertRaises(GroundedInputBudgetError) as error:
            trim_context_to_input_budget(
                empty,
                budget=GroundedInputBudget(effective_envelope_tokens=10, safety_margin_tokens=0),
                measure_context=_measure,
            )
        self.assertEqual(error.exception.detail, "Question is too large for the configured grounded-analysis input budget")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
