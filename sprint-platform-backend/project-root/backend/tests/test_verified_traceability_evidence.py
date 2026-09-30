"""Focused deterministic evidence/source/budget tests for Phase 12E."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from types import SimpleNamespace

from app.services.evidence_context_service import (
    BoundedEvidenceContext,
    EvidenceCategoryCoverage,
    EvidenceContextStats,
    EvidenceCoverage,
    rebuild_bounded_evidence_context,
)
from app.services.evidence_source_service import (
    EvidenceSource,
    EvidenceSourceType,
    build_evidence_sources,
)
from app.services.llm.citation_validator import validate_answer_citations
from app.services.llm.evidence_context_formatter import format_evidence_context
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.llm.input_budget_service import GroundedInputBudget, trim_context_to_input_budget
from app.services.llm.base import LLMGenerationResult
from app.services.llm.grounded_analysis_service import analyze_grounded_question
from app.services.query_intent_service import QueryIntent
from app.services.query_intent_service import classify_query_intent


def _source(
    kind: EvidenceSourceType,
    identifier: uuid.UUID,
    label: str,
    *,
    requirement_key: str | None = None,
    issue_key: str | None = None,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=label, source_type=kind, project_key="BLI", record_id=identifier,
        title=label, issue_key=issue_key, document_id=None, chunk_id=None, chunk_index=None,
        document_type=None, page_number=None, section_title=None, metadata={}, requirement_key=requirement_key,
    )


def _context() -> BoundedEvidenceContext:
    requirement_one = SimpleNamespace(
        id=uuid.uuid4(), requirement_key="BLI-REQ-001", statement="Thresholds shall be documented.",
        source_chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), document_title="Fixture PRD",
        document_type="PRD", chunk_index=0, page_number=None, section_title="Thresholds",
    )
    requirement_two = SimpleNamespace(
        id=uuid.uuid4(), requirement_key="BLI-REQ-002", statement="Inference shall be staged.",
        source_chunk_id=uuid.uuid4(), document_id=uuid.uuid4(), document_title="Fixture PRD",
        document_type="PRD", chunk_index=1, page_number=None, section_title="Release",
    )
    link_one = SimpleNamespace(
        id=uuid.uuid4(), requirement_id=requirement_one.id, requirement_key=requirement_one.requirement_key,
        link_kind="IMPLEMENTED_BY_ISSUE", target_type="ISSUE", target_id=uuid.uuid4(), target_label="BLI-11",
    )
    link_two = SimpleNamespace(
        id=uuid.uuid4(), requirement_id=requirement_two.id, requirement_key=requirement_two.requirement_key,
        link_kind="RELEASED_BY_DEPLOYMENT", target_type="DEPLOYMENT", target_id=uuid.uuid4(), target_label="BLI-12",
    )
    sources = [
        _source(EvidenceSourceType.REQUIREMENT, requirement_one.id, "REQ-1", requirement_key="BLI-REQ-001"),
        _source(EvidenceSourceType.REQUIREMENT, requirement_two.id, "REQ-2", requirement_key="BLI-REQ-002"),
        _source(EvidenceSourceType.TRACEABILITY, link_one.id, "TRACE-1", requirement_key="BLI-REQ-001"),
        _source(EvidenceSourceType.TRACEABILITY, link_two.id, "TRACE-2", requirement_key="BLI-REQ-002"),
    ]
    coverage = EvidenceCoverage(
        selected_scope="PROJECT",
        issues=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        tests=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        deployments=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        comments=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        documents=EvidenceCategoryCoverage(False, 0, 0, 0, None),
        requirements=EvidenceCategoryCoverage(True, 2, 2, 0, True),
        trace_links=EvidenceCategoryCoverage(True, 2, 2, 0, True),
    )
    stats = EvidenceContextStats(
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        len(sources), len(sources), False,
        available_requirements=2, included_requirements=2, omitted_requirements=0,
        available_trace_links=2, included_trace_links=2, omitted_trace_links=0,
    )
    return BoundedEvidenceContext(
        query="Which documented requirements have supporting delivered work?", project_key="BLI",
        intent=QueryIntent.HYBRID, employee_reference=None, sprint_reference=None,
        issues=[], tests=[], deployments=[], comments=[], documents=[], sources=sources, stats=stats,
        warnings=[], coverage=coverage, requirements=[requirement_one, requirement_two], trace_links=[link_one, link_two],
    )


def _context_with_linked_delivery_evidence() -> BoundedEvidenceContext:
    """A final-context-only fixture with every supported target represented."""
    context = _context()
    issue_one = SimpleNamespace(
        id=uuid.uuid4(), issue_key="BLI-11", title="Define deterministic risk thresholds",
        issue_type="STORY", status="DONE", story_points=None, assignee_name=None,
        sprint_name=None, description=None, acceptance_criteria=None, technical_notes=None,
        parent_issue_key=None, parent_issue_title=None, created_at=None, completed_at=None,
    )
    issue_two = SimpleNamespace(
        id=uuid.uuid4(), issue_key="BLI-12", title="Load model and run inference",
        issue_type="TASK", status="DONE", story_points=None, assignee_name=None,
        sprint_name=None, description=None, acceptance_criteria=None, technical_notes=None,
        parent_issue_key=None, parent_issue_title=None, created_at=None, completed_at=None,
    )
    test = SimpleNamespace(
        id=uuid.uuid4(), issue_id=issue_one.id, testing_status="PASSED",
        test_cases_total=12, test_cases_passed=12, bugs_found=None, reopened_count=None,
        tested_by_name=None, tested_at=None, testing_notes=None,
    )
    deployment = SimpleNamespace(
        id=uuid.uuid4(), issue_id=issue_two.id, deployment_status="STAGING",
        environment="model-service", deployment_date=None, production_notes=None,
        production_incidents=None,
    )
    issue_link = context.trace_links[0]
    deployment_link = context.trace_links[1]
    issue_link.target_id, issue_link.target_label = issue_one.id, "BLI-11"
    deployment_link.target_id, deployment_link.target_label = deployment.id, "Deployment for BLI-12"
    test_link = SimpleNamespace(
        id=uuid.uuid4(), requirement_id=context.requirements[0].id,
        requirement_key="BLI-REQ-001", link_kind="VERIFIED_BY_TEST", target_type="TEST",
        target_id=test.id, target_label="Test result for BLI-11",
    )
    sources = [
        _source(EvidenceSourceType.REQUIREMENT, context.requirements[0].id, "REQ-1", requirement_key="BLI-REQ-001"),
        _source(EvidenceSourceType.REQUIREMENT, context.requirements[1].id, "REQ-2", requirement_key="BLI-REQ-002"),
        _source(EvidenceSourceType.TRACEABILITY, issue_link.id, "TRACE-1", requirement_key="BLI-REQ-001"),
        _source(EvidenceSourceType.TRACEABILITY, test_link.id, "TRACE-2", requirement_key="BLI-REQ-001"),
        _source(EvidenceSourceType.TRACEABILITY, deployment_link.id, "TRACE-3", requirement_key="BLI-REQ-002"),
        _source(EvidenceSourceType.ISSUE, issue_one.id, "ISSUE-3", issue_key="BLI-11"),
        _source(EvidenceSourceType.ISSUE, issue_two.id, "ISSUE-4", issue_key="BLI-12"),
        _source(EvidenceSourceType.TEST, test.id, "TEST-2", issue_key="BLI-11"),
        _source(EvidenceSourceType.DEPLOYMENT, deployment.id, "DEPLOY-1", issue_key="BLI-12"),
    ]
    return replace(
        context,
        issues=[issue_one, issue_two],
        tests=[test],
        deployments=[deployment],
        trace_links=[issue_link, test_link, deployment_link],
        sources=sources,
        stats=replace(
            context.stats,
            available_issues=2, included_issues=2,
            available_tests=1, included_tests=1,
            available_deployments=1, included_deployments=1,
            available_sources=len(sources), included_sources=len(sources),
            available_trace_links=3, included_trace_links=3,
        ),
    )


class VerifiedTraceabilityEvidenceTests(unittest.TestCase):
    def test_source_registry_assigns_deterministic_req_and_trace_ids(self) -> None:
        context = _context()
        # The source builder receives already selected structured evidence.  It
        # must assign category-local labels before any later count/input bounds.
        package = SimpleNamespace(
            project_key="BLI",
            structured_evidence=SimpleNamespace(
                issues=[], tests=[], deployments=[], comments=[],
                requirements=context.requirements, trace_links=context.trace_links,
            ),
            document_evidence=None,
        )
        sources = build_evidence_sources(package)  # type: ignore[arg-type]
        self.assertEqual(
            [source.source_id for source in sources],
            ["REQ-1", "REQ-2", "TRACE-1", "TRACE-2"],
        )

    def test_formatter_groups_final_context_requirement_delivery_evidence(self) -> None:
        formatted = format_evidence_context(_context_with_linked_delivery_evidence())
        self.assertEqual(
            formatted.source_ids,
            ("REQ-1", "REQ-2", "TRACE-1", "TRACE-2", "TRACE-3", "ISSUE-3", "ISSUE-4", "TEST-2", "DEPLOY-1"),
        )
        self.assertIn("VERIFIED REQUIREMENT DELIVERY EVIDENCE", formatted.text)
        self.assertNotIn("\nVERIFIED REQUIREMENTS\n", formatted.text)
        self.assertNotIn("\nVERIFIED TRACEABILITY\n", formatted.text)
        self.assertIn("Requirement citation ID: REQ-1", formatted.text)
        self.assertIn("Requirement key: BLI-REQ-001", formatted.text)
        self.assertIn("Requirement statement: Thresholds shall be documented.", formatted.text)
        self.assertIn("Trace citation ID: TRACE-1", formatted.text)
        self.assertIn("Explicit relationship: IMPLEMENTED_BY_ISSUE → BLI-11", formatted.text)
        self.assertIn("Issue evidence citation ID ISSUE-3: BLI-11 | DONE | Define deterministic risk thresholds", formatted.text)
        self.assertIn("Trace citation ID: TRACE-2", formatted.text)
        self.assertIn("Test evidence citation ID TEST-2: PASSED | 12 / 12 test cases passed", formatted.text)
        self.assertIn("Trace citation ID: TRACE-3", formatted.text)
        self.assertIn("Deployment evidence citation ID DEPLOY-1: STAGING | model-service", formatted.text)

    def test_grouped_trace_omits_target_details_when_final_context_lacks_target(self) -> None:
        context = _context_with_linked_delivery_evidence()
        retained_sources = [
            source for source in context.sources
            if source.source_type in {EvidenceSourceType.REQUIREMENT, EvidenceSourceType.TRACEABILITY}
        ]
        without_targets = replace(
            context,
            issues=[], tests=[], deployments=[], sources=retained_sources,
            stats=replace(context.stats, included_issues=0, included_tests=0, included_deployments=0),
        )

        formatted = format_evidence_context(without_targets)

        self.assertIn("Trace citation ID: TRACE-1", formatted.text)
        self.assertIn("Explicit relationship: IMPLEMENTED_BY_ISSUE → BLI-11", formatted.text)
        self.assertNotIn("Issue evidence citation ID", formatted.text)
        self.assertNotIn("Test evidence citation ID", formatted.text)
        self.assertNotIn("Deployment evidence citation ID", formatted.text)

    def test_removing_requirement_removes_its_trace_source_without_renumbering(self) -> None:
        context = _context()
        rebuilt = rebuild_bounded_evidence_context(
            context,
            issues=[], tests=[], deployments=[], comments=[], documents=[],
            requirements=context.requirements[:1], trace_links=context.trace_links[:1],
            input_budget_truncated=True,
        )
        self.assertEqual([source.source_id for source in rebuilt.sources], ["REQ-1", "TRACE-1"])
        self.assertEqual([link.requirement_id for link in rebuilt.trace_links], [rebuilt.requirements[0].id])

    def test_budget_never_retains_trace_without_requirement(self) -> None:
        context = _context()
        budgeted = trim_context_to_input_budget(
            context,
            budget=GroundedInputBudget(effective_envelope_tokens=100, safety_margin_tokens=0),
            measure_context=lambda value: len(value.requirements) * 100 + len(value.trace_links) * 10,
        )
        requirement_ids = {item.id for item in budgeted.requirements}
        self.assertTrue(all(link.requirement_id in requirement_ids for link in budgeted.trace_links))

    def test_unknown_canonical_trace_id_remains_invalid(self) -> None:
        formatted = format_evidence_context(_context())
        answer = GroundedAnswer.model_validate({
            "answer": "Unsupported link.",
            "claims": [{"statement": "Unsupported.", "source_ids": ["TRACE-99"]}],
            "limitations": [],
        })
        validation = validate_answer_citations(answer, formatted)
        self.assertFalse(validation.valid)
        self.assertEqual(validation.invalid_source_ids, ("TRACE-99",))

    def test_bli_requirement_delivery_question_routes_and_accepts_explicit_links(self) -> None:
        question = "Which documented requirements have supporting delivered work?"
        intent = classify_query_intent(question)
        self.assertEqual(intent.query, question)
        self.assertEqual(intent.intent, QueryIntent.HYBRID)
        self.assertTrue(intent.needs_verified_traceability_evidence)

        class FakeLLM:
            def generate(self, request: object) -> LLMGenerationResult:
                return LLMGenerationResult(
                    content=(
                        '{"answer":"One requirement has an explicit verified issue link.",'
                        '"claims":[{"statement":"BLI-REQ-001 is explicitly linked to BLI-11.",'
                        '"source_ids":["REQ-1","TRACE-1"]}],"limitations":['
                        '"Only explicitly persisted trace links are included."]}'
                    ),
                    provider="test", model="test",
                )

        result = analyze_grounded_question(question, _context(), FakeLLM())  # type: ignore[arg-type]
        self.assertTrue(result.citation_validation.valid)
        self.assertEqual(result.citation_validation.valid_source_ids, ("REQ-1", "TRACE-1"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
