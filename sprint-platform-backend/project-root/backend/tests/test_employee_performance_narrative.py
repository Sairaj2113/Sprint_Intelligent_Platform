"""No-network tests for deterministic, attribution-safe performance narratives."""

from __future__ import annotations

from dataclasses import replace
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
)
from app.services.evidence_source_service import EvidenceSource, EvidenceSourceType
from app.services.llm.citation_validator import validate_answer_citations
from app.services.llm.employee_performance_narrative import (
    EmployeePerformanceNarrativePlan,
    EmployeePerformanceNarrativeValidationError,
    PerformanceNarrativeSection,
    build_employee_performance_fact_inventory,
    build_employee_performance_selection_prompt,
    has_employee_performance_evidence,
    render_employee_performance_narrative,
    validate_employee_performance_narrative_plan,
)
from app.services.llm.evidence_context_formatter import FormattedEvidenceContext
from app.services.llm.evidence_sufficiency import EvidenceSufficiencyStatus, assess_evidence_sufficiency
from app.services.query_intent_service import QueryIntent


EMPLOYEE_ID = UUID("11111111-1111-1111-1111-111111111111")
ISSUE_ID = UUID("22222222-2222-2222-2222-222222222222")
TEST_ID = UUID("33333333-3333-3333-3333-333333333333")
DEPLOYMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
REQUIREMENT_ID = UUID("55555555-5555-5555-5555-555555555555")
TRACE_ID = UUID("66666666-6666-6666-6666-666666666666")


def _report() -> EmployeePerformanceReport:
    return EmployeePerformanceReport(
        employee=EmployeePerformanceEmployee(
            id=EMPLOYEE_ID, employee_code="EMP001", name="Sairaj Pankar",
            role="Engineer", department="Engineering",
        ),
        project=EmployeePerformanceProject(id=UUID(int=7), project_key="BLI", name="Bank Loan"),
        scope=EmployeePerformanceScope(
            kind="PROJECT", sprint_id=None, sprint_name=None, definition="Assigned project issues.",
        ),
        delivery=EmployeeDeliveryMetrics(
            assigned_issue_count=3, completed_issue_count=2, completion_rate_percentage=66.7,
            completion_rate_eligible_issue_count=3,
            status_distribution=EmployeeIssueStatusDistribution(
                backlog=0, selected_for_sprint=0, todo=1, in_progress=0, code_review=0,
                testing=0, ready_for_release=0, done=2,
            ),
            assigned_story_points=8, completed_story_points=5, assigned_bug_count=1,
            resolved_bug_count=1, reopened_assigned_issue_count=0, total_reopen_count=0,
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
            explicit_implemented_requirement_keys=["BLI-REQ-002"],
            explicit_implemented_requirement_link_count=1,
        ),
        documented_activity=EmployeeDocumentedActivityMetrics(
            authored_comment_count=1, issues_commented_on_count=1,
        ),
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
        title=source_id, issue_key="BLI-12", document_id=None, chunk_id=None,
        chunk_index=None, document_type=None, page_number=None, section_title=None, metadata={},
        requirement_key="BLI-REQ-002" if source_type is EvidenceSourceType.REQUIREMENT else None,
    )


def _context(*, retain_raw: bool = True) -> BoundedEvidenceContext:
    sources = [_source("KPI-1", EvidenceSourceType.KPI, EMPLOYEE_ID)]
    issues: list[object] = []
    tests: list[object] = []
    deployments: list[object] = []
    requirements: list[object] = []
    trace_links: list[object] = []
    if retain_raw:
        sources.extend((
            _source("ISSUE-1", EvidenceSourceType.ISSUE, ISSUE_ID),
            _source("TEST-1", EvidenceSourceType.TEST, TEST_ID),
            _source("DEPLOY-1", EvidenceSourceType.DEPLOYMENT, DEPLOYMENT_ID),
            _source("REQ-1", EvidenceSourceType.REQUIREMENT, REQUIREMENT_ID),
            _source("TRACE-1", EvidenceSourceType.TRACEABILITY, TRACE_ID),
        ))
        issues = [SimpleNamespace(id=ISSUE_ID, issue_key="BLI-12")]
        tests = [SimpleNamespace(id=TEST_ID, issue_id=ISSUE_ID, testing_status="PASSED")]
        deployments = [SimpleNamespace(
            id=DEPLOYMENT_ID, issue_id=ISSUE_ID, deployment_status="STAGING", environment="staging",
        )]
        requirements = [SimpleNamespace(id=REQUIREMENT_ID, requirement_key="BLI-REQ-002")]
        trace_links = [SimpleNamespace(
            id=TRACE_ID, requirement_id=REQUIREMENT_ID, link_kind="IMPLEMENTED_BY_ISSUE",
            target_label="BLI-12", target_type="ISSUE", target_id=ISSUE_ID,
        )]
    stats = EvidenceContextStats(
        available_issues=len(issues), included_issues=len(issues), omitted_issues=0,
        available_tests=len(tests), included_tests=len(tests), omitted_tests=0,
        available_deployments=len(deployments), included_deployments=len(deployments), omitted_deployments=0,
        available_comments=0, included_comments=0, omitted_comments=0,
        available_documents=0, included_documents=0, omitted_documents=0,
        available_sources=len(sources), included_sources=len(sources), truncated=False,
        available_requirements=len(requirements), included_requirements=len(requirements), omitted_requirements=0,
        available_trace_links=len(trace_links), included_trace_links=len(trace_links), omitted_trace_links=0,
    )
    complete = lambda count: EvidenceCategoryCoverage(True, count, count, 0, True)
    return BoundedEvidenceContext(
        query="How has EMP001 performed on BLI?", project_key="BLI", intent=QueryIntent.STRUCTURED,
        employee_reference="EMP001", sprint_reference=None, issues=issues, tests=tests,
        deployments=deployments, comments=[], documents=[], requirements=requirements,
        trace_links=trace_links, sources=sources, stats=stats, warnings=[],
        coverage=EvidenceCoverage(
            selected_scope="EMPLOYEE_ASSIGNED", issues=complete(len(issues)), tests=complete(len(tests)),
            deployments=complete(len(deployments)), comments=complete(0),
            documents=EvidenceCategoryCoverage(False, 0, 0, 0, None),
            requirements=complete(len(requirements)), trace_links=complete(len(trace_links)),
        ),
        employee_performance=_report(),
    )


class EmployeePerformanceNarrativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = _context()
        self.inventory = build_employee_performance_fact_inventory(self.context)
        self.final_context = FormattedEvidenceContext(
            text="final budgeted evidence",
            source_ids=tuple(source.source_id for source in self.context.sources),
            truncated=False,
        )

    def _plan(self, **overrides: list[str]) -> EmployeePerformanceNarrativePlan:
        payload = {section.value: [] for section in PerformanceNarrativeSection}
        payload.update(overrides)
        return EmployeePerformanceNarrativePlan.model_validate(payload)

    def test_inventory_is_deterministic_and_uses_only_retained_context_records(self) -> None:
        second = build_employee_performance_fact_inventory(self.context)
        self.assertEqual(self.inventory, second)
        self.assertIn("quality.linked_test.TEST-1", self.inventory.fact_ids)
        self.assertIn("deployment.linked_record.DEPLOY-1", self.inventory.fact_ids)
        self.assertIn("requirements.explicit_trace.TRACE-1", self.inventory.fact_ids)
        trimmed_inventory = build_employee_performance_fact_inventory(_context(retain_raw=False))
        self.assertNotIn("quality.linked_test.TEST-1", trimmed_inventory.fact_ids)
        self.assertNotIn("deployment.linked_record.DEPLOY-1", trimmed_inventory.fact_ids)
        self.assertNotIn("requirements.explicit_trace.TRACE-1", trimmed_inventory.fact_ids)

    def test_selection_prompt_contains_internal_fact_ids_only_and_fixed_sections(self) -> None:
        prompt = build_employee_performance_selection_prompt("How has EMP001 performed?", self.inventory)
        self.assertIn("quality.linked_test.TEST-1", prompt)
        self.assertNotIn("BLI-REQ-002", prompt)
        self.assertNotIn("KPI-1", prompt)
        self.assertIn("Quality and Verification", prompt)
        self.assertIn("Every field must be a list of fact IDs", prompt)

    def test_renderer_uses_safe_test_deployment_and_requirement_templates(self) -> None:
        plan = self._plan(
            quality_verification=["quality.linked_test.TEST-1"],
            deployment_evidence=["deployment.linked_record.DEPLOY-1"],
            requirement_connections=[
                "requirements.kpi_explicit_connection_summary",
                "requirements.explicit_trace.TRACE-1",
            ],
        )
        selected = validate_employee_performance_narrative_plan(plan, self.inventory, self.final_context)
        answer = render_employee_performance_narrative(selected, self.inventory)
        text = answer.answer.casefold()
        self.assertIn("linked to assigned issue bli-12", text)
        self.assertIn("does not establish that the employee performed testing", text)
        self.assertIn("does not establish that the employee performed a deployment", text)
        self.assertIn("bli-req-002", text)
        self.assertIn("explicitly recorded implemented_by_issue relationship to bli-12", text)
        self.assertNotIn("employee completed a deployment", text)
        self.assertEqual(
            [claim.source_ids for claim in answer.claims],
            [
                ["KPI-1", "ISSUE-1", "TEST-1"],
                ["KPI-1", "ISSUE-1", "DEPLOY-1"],
                ["KPI-1"],
                ["REQ-1", "TRACE-1"],
            ],
        )
        headings = [
            "Delivery", "Quality and Verification", "Deployment Evidence",
            "Requirement Connections", "Documented Activity", "Lifecycle Timing", "Limitations",
        ]
        self.assertEqual([answer.answer.index(heading) for heading in headings], sorted(answer.answer.index(heading) for heading in headings))

    def test_kpi_requirement_summary_never_infers_a_specific_target(self) -> None:
        plan = self._plan(requirement_connections=["requirements.kpi_explicit_connection_summary"])
        selected = validate_employee_performance_narrative_plan(plan, self.inventory, self.final_context)
        answer = render_employee_performance_narrative(selected, self.inventory)
        kpi_statement = answer.claims[0].statement
        self.assertIn("BLI-REQ-002", kpi_statement)
        self.assertNotIn("BLI-12", kpi_statement)
        self.assertEqual(answer.claims[0].source_ids, ["KPI-1"])

    def test_comments_lifecycle_and_story_points_preserve_attribution_boundaries(self) -> None:
        plan = self._plan(
            delivery=["delivery.story_points"],
            documented_activity=["activity.authored_comments"],
            lifecycle_timing=["timing.average_cycle_time"],
        )
        answer = render_employee_performance_narrative(
            validate_employee_performance_narrative_plan(plan, self.inventory, self.final_context),
            self.inventory,
        )
        text = answer.answer.casefold()
        self.assertIn("not measures of effort or productivity", text)
        self.assertIn("comment authorship does not establish issue implementation or ownership", text)
        self.assertIn("not employee work time", text)

    def test_assignment_completion_and_null_denominators_remain_factual(self) -> None:
        report = _report()
        zero_report = report.model_copy(update={
            "delivery": report.delivery.model_copy(update={
                "completion_rate_percentage": None,
                "completion_rate_eligible_issue_count": 0,
            }),
            "quality": report.quality.model_copy(update={
                "test_case_pass_rate_percentage": None,
                "test_case_pass_rate_eligible_record_count": 0,
            }),
        })
        inventory = build_employee_performance_fact_inventory(
            replace(self.context, employee_performance=zero_report)
        )
        statements = {fact.fact_id: fact.statement.casefold() for fact in inventory.facts}
        self.assertIn("does not establish sole implementation", statements["delivery.assigned_issue_count"])
        self.assertIn("does not establish sole implementation", statements["delivery.completed_issue_count"])
        self.assertIn("no recorded completion ratio is available", statements["delivery.completion_rate_unavailable"])
        self.assertIn("no recorded test-case pass ratio is available", statements["quality.test_case_summary_unavailable"])

    def test_plan_validation_fails_closed_for_unknown_duplicate_unavailable_and_wrong_section(self) -> None:
        cases = (
            self._plan(delivery=["unknown.fact"]),
            self._plan(delivery=["delivery.story_points", "delivery.story_points"]),
            self._plan(delivery=["quality.linked_test.TEST-1"]),
        )
        missing_test_context = FormattedEvidenceContext("", ("KPI-1",), False)
        for plan in cases:
            with self.subTest(plan=plan):
                with self.assertRaises(EmployeePerformanceNarrativeValidationError):
                    validate_employee_performance_narrative_plan(plan, self.inventory, self.final_context)
        with self.assertRaises(EmployeePerformanceNarrativeValidationError):
            validate_employee_performance_narrative_plan(
                self._plan(quality_verification=["quality.linked_test.TEST-1"]),
                self.inventory,
                missing_test_context,
            )

    def test_backend_owned_claims_pass_existing_exact_citation_validation(self) -> None:
        plan = self._plan(
            delivery=["delivery.assigned_issue_count"],
            quality_verification=["quality.linked_test.TEST-1"],
        )
        answer = render_employee_performance_narrative(
            validate_employee_performance_narrative_plan(plan, self.inventory, self.final_context),
            self.inventory,
        )
        validation = validate_answer_citations(answer, self.final_context)
        self.assertTrue(validation.valid)
        self.assertEqual(validation.valid_source_ids, ("KPI-1", "ISSUE-1", "TEST-1"))

    def test_empty_valid_selection_is_limited_and_missing_evidence_is_not_negative_judgment(self) -> None:
        answer = render_employee_performance_narrative(
            validate_employee_performance_narrative_plan(self._plan(), self.inventory, self.final_context),
            self.inventory,
        )
        validation = validate_answer_citations(answer, self.final_context)
        sufficiency = assess_evidence_sufficiency(answer, self.final_context, validation)
        self.assertEqual(sufficiency.status, EvidenceSufficiencyStatus.LIMITED)
        self.assertIn("No factual statements were selected", answer.answer)
        self.assertNotIn("poor performance", answer.answer.casefold())

    def test_only_actual_performance_reports_activate_special_path(self) -> None:
        self.assertTrue(has_employee_performance_evidence(self.context))
        self.assertFalse(has_employee_performance_evidence(SimpleNamespace(employee_performance=object())))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
