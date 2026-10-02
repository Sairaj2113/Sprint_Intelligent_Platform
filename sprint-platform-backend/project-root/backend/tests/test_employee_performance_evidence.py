"""Focused no-network tests for Phase 13B KPI evidence integration."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import UUID

from app.schemas.employee_performance import (
    EmployeeDeliveryMetrics,
    EmployeeDeploymentMetrics,
    EmployeeDocumentedActivityMetrics,
    EmployeeIssueStatusDistribution,
    EmployeeLifecycleTimingMetrics,
    EmployeePerformanceEmployee,
    EmployeePerformanceProject,
    EmployeePerformanceReport,
    EmployeePerformanceScope,
    EmployeeQualityMetrics,
    EmployeeRequirementConnectionMetrics,
)
from app.services.evidence_context_service import (
    BoundedEvidenceContext,
    EvidenceCategoryCoverage,
    EvidenceContextStats,
    EvidenceCoverage,
    rebuild_bounded_evidence_context,
)
from app.services.evidence_source_service import EvidenceSource, EvidenceSourceType, build_evidence_sources
from app.services.llm.citation_validator import validate_answer_citations
from app.services.llm.evidence_context_formatter import format_evidence_context
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.query_intent_service import QueryIntent, classify_query_intent


EMPLOYEE_ID = UUID("11111111-1111-1111-1111-111111111111")
ISSUE_ID = UUID("22222222-2222-2222-2222-222222222222")


def _report() -> EmployeePerformanceReport:
    return EmployeePerformanceReport(
        employee=EmployeePerformanceEmployee(
            id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj Pankar", role="Engineer", department="Engineering"
        ),
        project=EmployeePerformanceProject(id=UUID(int=3), project_key="BLI", name="Bank Loan"),
        scope=EmployeePerformanceScope(kind="PROJECT", sprint_id=None, sprint_name=None, definition="Assigned project issues."),
        delivery=EmployeeDeliveryMetrics(
            assigned_issue_count=3, completed_issue_count=2, completion_rate_percentage=66.6666666667,
            completion_rate_eligible_issue_count=3,
            status_distribution=EmployeeIssueStatusDistribution(
                backlog=0, selected_for_sprint=0, todo=1, in_progress=0, code_review=0,
                testing=0, ready_for_release=0, done=2,
            ),
            assigned_story_points=8, completed_story_points=5, assigned_bug_count=0,
            resolved_bug_count=0, reopened_assigned_issue_count=0, total_reopen_count=0,
        ),
        quality=EmployeeQualityMetrics(
            completed_assigned_issue_count=2, completed_issues_with_test_evidence=1,
            completed_issues_without_test_evidence=1, linked_test_result_count=1,
            test_records_with_valid_case_counts=1, test_cases_total=10, test_cases_passed=9,
            test_cases_failed=1, test_case_pass_rate_percentage=90.0,
            test_case_pass_rate_eligible_record_count=1,
        ),
        deployment_evidence=EmployeeDeploymentMetrics(
            assigned_issues_with_deployment_evidence=1, deployment_record_count=1,
            not_deployed_count=0, staging_count=1, production_count=0, failed_count=0,
            environment_counts={"staging": 1}, deployments_without_recorded_environment=0,
        ),
        requirement_connections=EmployeeRequirementConnectionMetrics(
            explicit_implemented_requirement_keys=["BLI-REQ-001"],
            explicit_implemented_requirement_link_count=1,
        ),
        documented_activity=EmployeeDocumentedActivityMetrics(authored_comment_count=1, issues_commented_on_count=1),
        lifecycle_timing=EmployeeLifecycleTimingMetrics(
            cycle_time_eligible_issue_count=1, average_cycle_time_hours=48.0,
            development_time_eligible_issue_count=1, average_development_time_hours=24.0,
            review_time_eligible_issue_count=0, average_review_time_hours=None,
            testing_time_eligible_issue_count=0, average_testing_time_hours=None,
        ),
        limitations=["Issue assignment records assignment, not sole implementation or employee effort."],
    )


def _source(source_id: str, source_type: EvidenceSourceType, record_id: UUID) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id, source_type=source_type, project_key="BLI", record_id=record_id,
        title=source_id, issue_key="BLI-1" if source_type is EvidenceSourceType.ISSUE else None,
        document_id=None, chunk_id=None, chunk_index=None, document_type=None,
        page_number=None, section_title=None, metadata={},
    )


def _context(*, issues: list[object] | None = None, sources: list[EvidenceSource] | None = None) -> BoundedEvidenceContext:
    issues = issues or []
    sources = sources or []
    stats = EvidenceContextStats(
        available_issues=len(issues), included_issues=len(issues), omitted_issues=0,
        available_tests=0, included_tests=0, omitted_tests=0,
        available_deployments=0, included_deployments=0, omitted_deployments=0,
        available_comments=0, included_comments=0, omitted_comments=0,
        available_documents=0, included_documents=0, omitted_documents=0,
        available_sources=len(sources), included_sources=len(sources), truncated=False,
    )
    coverage = EvidenceCoverage(
        selected_scope="EMPLOYEE_ASSIGNED",
        issues=EvidenceCategoryCoverage(True, len(issues), len(issues), 0, True),
        tests=EvidenceCategoryCoverage(True, 0, 0, 0, True),
        deployments=EvidenceCategoryCoverage(True, 0, 0, 0, True),
        comments=EvidenceCategoryCoverage(True, 0, 0, 0, True),
        documents=EvidenceCategoryCoverage(False, 0, 0, 0, None),
    )
    return BoundedEvidenceContext(
        query="How did Sairaj perform on BLI?", project_key="BLI", intent=QueryIntent.STRUCTURED,
        employee_reference="Sairaj", sprint_reference=None, issues=issues, tests=[], deployments=[], comments=[],
        documents=[], sources=sources, stats=stats, warnings=[], coverage=coverage,
        employee_performance=_report(),
    )


class EmployeePerformanceEvidenceTests(unittest.TestCase):
    def test_explicit_employee_performance_questions_select_structured_kpi_evidence(self) -> None:
        for question in (
            "How did Sairaj perform on BLI?",
            "How has EMP001 performed on the BLI project?",
            "Show Sairaj's performance",
            "What are Sairaj's KPIs?",
            "Show performance report for EMP001",
            "What is Sairaj's completion rate?",
            "How many assigned issues has Sairaj completed?",
        ):
            with self.subTest(question=question):
                result = classify_query_intent(question)
                self.assertEqual(result.intent, QueryIntent.STRUCTURED)
                self.assertTrue(result.needs_employee_performance_evidence)
                self.assertTrue(result.needs_structured_evidence)

        sprint_result = classify_query_intent("How did Sairaj perform in Production Hardening?")
        self.assertEqual(sprint_result.sprint_reference, "Production Hardening")

    def test_kpi_source_is_deterministic_and_precedes_no_new_raw_evidence(self) -> None:
        package = SimpleNamespace(
            project_key="BLI",
            structured_evidence=SimpleNamespace(
                employee_performance=_report(), issues=[], tests=[], deployments=[], comments=[],
                requirements=[], trace_links=[],
            ),
            document_evidence=None,
        )

        sources = build_evidence_sources(package)

        self.assertEqual([source.source_id for source in sources], ["KPI-1"])
        self.assertEqual(sources[0].source_type, EvidenceSourceType.KPI)
        self.assertEqual(sources[0].record_id, EMPLOYEE_ID)
        self.assertEqual(sources[0].employee_performance, _report())

    def test_formatter_renders_metrics_with_kpi_citation_and_no_score_language(self) -> None:
        context = _context(sources=[_source("KPI-1", EvidenceSourceType.KPI, EMPLOYEE_ID)])

        formatted = format_evidence_context(context)

        self.assertEqual(formatted.source_ids, ("KPI-1",))
        self.assertIn("EMPLOYEE PERFORMANCE EVIDENCE", formatted.text)
        self.assertIn("Citation ID: KPI-1", formatted.text)
        self.assertIn("assigned issues=3", formatted.text)
        self.assertIn("Completion rate percentage", formatted.text)
        self.assertIn("BLI-REQ-001", formatted.text)
        self.assertIn("VERIFIED REQUIREMENT RECORDS", formatted.text)
        self.assertIn("No separate record-level REQ-n evidence was selected", formatted.text)
        self.assertIn("VERIFIED TRACEABILITY RECORDS", formatted.text)
        self.assertIn("No separate record-level TRACE-n evidence was selected", formatted.text)
        self.assertNotIn("No verified requirement evidence.", formatted.text)
        self.assertNotIn("No verified trace links.", formatted.text)
        self.assertNotIn("performance score", formatted.text.casefold())

    def test_kpi_requirement_summary_supports_only_its_aggregate_statement(self) -> None:
        context = _context(sources=[_source("KPI-1", EvidenceSourceType.KPI, EMPLOYEE_ID)])
        formatted = format_evidence_context(context)
        answer = GroundedAnswer.model_validate({
            "answer": "The deterministic report records one explicit connection.",
            "claims": [{
                "statement": "The employee performance report records one explicit implemented requirement connection: BLI-REQ-001.",
                "source_ids": ["KPI-1"],
            }],
            "limitations": [],
        })

        validation = validate_answer_citations(answer, formatted)

        self.assertTrue(validation.valid)
        self.assertEqual(validation.valid_source_ids, ("KPI-1",))

    def test_non_employee_context_preserves_existing_missing_requirement_wording(self) -> None:
        context = _context(sources=[])
        non_employee_context = BoundedEvidenceContext(
            query=context.query, project_key=context.project_key, intent=context.intent,
            employee_reference=None, sprint_reference=context.sprint_reference,
            issues=context.issues, tests=context.tests, deployments=context.deployments,
            comments=context.comments, documents=context.documents, sources=[],
            stats=EvidenceContextStats(
                available_issues=0, included_issues=0, omitted_issues=0,
                available_tests=0, included_tests=0, omitted_tests=0,
                available_deployments=0, included_deployments=0, omitted_deployments=0,
                available_comments=0, included_comments=0, omitted_comments=0,
                available_documents=0, included_documents=0, omitted_documents=0,
                available_sources=0, included_sources=0, truncated=False,
            ),
            warnings=[], coverage=context.coverage, employee_performance=None,
        )

        formatted = format_evidence_context(non_employee_context)

        self.assertIn("VERIFIED REQUIREMENTS\n- No verified requirement evidence.", formatted.text)
        self.assertIn("VERIFIED TRACEABILITY\n- No verified trace links.", formatted.text)
        self.assertNotIn("No separate record-level REQ-n evidence", formatted.text)

    def test_budget_rebuild_preserves_kpi_source_and_removes_only_omitted_raw_source(self) -> None:
        issue = SimpleNamespace(id=ISSUE_ID)
        context = _context(
            issues=[issue],
            sources=[
                _source("KPI-1", EvidenceSourceType.KPI, EMPLOYEE_ID),
                _source("ISSUE-1", EvidenceSourceType.ISSUE, ISSUE_ID),
            ],
        )

        rebuilt = rebuild_bounded_evidence_context(
            context, issues=[], tests=[], deployments=[], comments=[], documents=[],
            requirements=[], trace_links=[], input_budget_truncated=True,
        )

        self.assertEqual([source.source_id for source in rebuilt.sources], ["KPI-1"])
        self.assertEqual(rebuilt.employee_performance, context.employee_performance)
        self.assertTrue(rebuilt.stats.truncated)

    def test_exact_citation_validation_accepts_kpi_and_rejects_absent_kpi(self) -> None:
        context = _context(sources=[_source("KPI-1", EvidenceSourceType.KPI, EMPLOYEE_ID)])
        formatted = format_evidence_context(context)
        valid = GroundedAnswer.model_validate({
            "answer": "Recorded metrics are available.",
            "claims": [{"statement": "Three assigned issues are recorded.", "source_ids": ["KPI-1"]}],
            "limitations": [],
        })
        invalid = GroundedAnswer.model_validate({
            "answer": "Recorded metrics are available.",
            "claims": [{"statement": "Unsupported.", "source_ids": ["KPI-2"]}],
            "limitations": [],
        })

        self.assertTrue(validate_answer_citations(valid, formatted).valid)
        result = validate_answer_citations(invalid, formatted)
        self.assertFalse(result.valid)
        self.assertEqual(result.invalid_source_ids, ("KPI-2",))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
