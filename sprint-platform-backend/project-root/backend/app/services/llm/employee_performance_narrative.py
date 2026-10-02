"""Deterministic, attribution-safe employee-performance narrative rendering."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.schemas.employee_performance import EmployeePerformanceReport
from app.services.evidence_source_service import EvidenceSourceType
from app.services.llm.grounded_answer import GroundedAnswer, GroundedClaim

if TYPE_CHECKING:
    from app.services.evidence_context_service import BoundedEvidenceContext
    from app.services.llm.evidence_context_formatter import FormattedEvidenceContext


class PerformanceNarrativeSection(str, Enum):
    DELIVERY = "delivery"
    QUALITY_VERIFICATION = "quality_verification"
    DEPLOYMENT_EVIDENCE = "deployment_evidence"
    REQUIREMENT_CONNECTIONS = "requirement_connections"
    DOCUMENTED_ACTIVITY = "documented_activity"
    LIFECYCLE_TIMING = "lifecycle_timing"
    LIMITATIONS = "limitations"


SECTION_LABELS = {
    PerformanceNarrativeSection.DELIVERY: "Delivery",
    PerformanceNarrativeSection.QUALITY_VERIFICATION: "Quality and Verification",
    PerformanceNarrativeSection.DEPLOYMENT_EVIDENCE: "Deployment Evidence",
    PerformanceNarrativeSection.REQUIREMENT_CONNECTIONS: "Requirement Connections",
    PerformanceNarrativeSection.DOCUMENTED_ACTIVITY: "Documented Activity",
    PerformanceNarrativeSection.LIFECYCLE_TIMING: "Lifecycle Timing",
    PerformanceNarrativeSection.LIMITATIONS: "Limitations",
}


class EmployeePerformanceNarrativeValidationError(Exception):
    """Raised when a provider-selected performance fact plan is invalid."""


class EmployeePerformanceNarrativePlan(BaseModel):
    """Strict provider output: selections only, never factual prose or citations."""

    model_config = ConfigDict(extra="forbid")

    delivery: list[StrictStr] = Field(default_factory=list)
    quality_verification: list[StrictStr] = Field(default_factory=list)
    deployment_evidence: list[StrictStr] = Field(default_factory=list)
    requirement_connections: list[StrictStr] = Field(default_factory=list)
    documented_activity: list[StrictStr] = Field(default_factory=list)
    lifecycle_timing: list[StrictStr] = Field(default_factory=list)
    limitations: list[StrictStr] = Field(default_factory=list)

    @field_validator(
        "delivery",
        "quality_verification",
        "deployment_evidence",
        "requirement_connections",
        "documented_activity",
        "lifecycle_timing",
        "limitations",
    )
    @classmethod
    def fact_ids_must_not_be_blank(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("fact IDs must not be blank")
        return values


@dataclass(frozen=True)
class EmployeePerformanceNarrativeFact:
    fact_id: str
    section: PerformanceNarrativeSection
    statement: str
    citation_ids: tuple[str, ...] = ()
    limitation: bool = False


@dataclass(frozen=True)
class EmployeePerformanceFactInventory:
    facts: tuple[EmployeePerformanceNarrativeFact, ...]
    baseline_limitations: tuple[str, ...]

    @property
    def fact_ids(self) -> tuple[str, ...]:
        return tuple(fact.fact_id for fact in self.facts)


def has_employee_performance_evidence(context: object) -> bool:
    """Only actual Phase 13A reports activate the special narrative path."""
    return isinstance(getattr(context, "employee_performance", None), EmployeePerformanceReport)


def build_employee_performance_fact_inventory(
    context: BoundedEvidenceContext,
) -> EmployeePerformanceFactInventory:
    """Create safe facts solely from the final, already-budgeted context."""
    report = context.employee_performance
    if not isinstance(report, EmployeePerformanceReport):
        raise EmployeePerformanceNarrativeValidationError("Employee performance evidence is unavailable")

    sources = list(context.sources)
    source_ids = {source.source_id for source in sources}
    kpi_source = _first_source_of_type(sources, EvidenceSourceType.KPI)
    facts: list[EmployeePerformanceNarrativeFact] = []

    def add(
        fact_id: str,
        section: PerformanceNarrativeSection,
        statement: str,
        citation_ids: tuple[str, ...] = (),
        *,
        limitation: bool = False,
    ) -> None:
        if all(source_id in source_ids for source_id in citation_ids):
            facts.append(EmployeePerformanceNarrativeFact(fact_id, section, statement, citation_ids, limitation))

    if kpi_source is not None:
        kpi = kpi_source.source_id
        delivery = report.delivery
        employee_code = report.employee.employee_code
        add("delivery.assigned_issue_count", PerformanceNarrativeSection.DELIVERY, f"The employee performance report records {delivery.assigned_issue_count} assigned issue(s) for {employee_code}; recorded assignment does not establish sole implementation.", (kpi,))
        add("delivery.completed_issue_count", PerformanceNarrativeSection.DELIVERY, f"The employee performance report records {delivery.completed_issue_count} completed assigned issue(s); this is issue completion status and does not establish sole implementation.", (kpi,))
        if delivery.completion_rate_percentage is not None:
            add("delivery.completion_rate", PerformanceNarrativeSection.DELIVERY, f"The recorded completion ratio is {_format_number(delivery.completion_rate_percentage)}% across {delivery.completion_rate_eligible_issue_count} eligible assigned issue(s).", (kpi,))
        else:
            add("delivery.completion_rate_unavailable", PerformanceNarrativeSection.DELIVERY, "No recorded completion ratio is available because there are no eligible assigned issues.", (kpi,))
        add("delivery.story_points", PerformanceNarrativeSection.DELIVERY, f"The report records {delivery.assigned_story_points} assigned and {delivery.completed_story_points} completed story-point estimates; these are estimates, not measures of effort or productivity.", (kpi,))
        add("delivery.bug_counts", PerformanceNarrativeSection.DELIVERY, f"The report records {delivery.assigned_bug_count} assigned bug(s) and {delivery.resolved_bug_count} resolved bug(s) within the assigned-issue scope; this does not establish individual bug resolution.", (kpi,))

        quality = report.quality
        add("quality.summary", PerformanceNarrativeSection.QUALITY_VERIFICATION, f"The report records {quality.linked_test_result_count} test record(s) linked to assigned issues; linked testing evidence does not establish that {employee_code} performed testing.", (kpi,))
        if quality.test_case_pass_rate_percentage is not None:
            add("quality.test_case_summary", PerformanceNarrativeSection.QUALITY_VERIFICATION, f"Recorded valid test-case counts show {quality.test_cases_passed} passed of {quality.test_cases_total} total ({_format_number(quality.test_case_pass_rate_percentage)}%).", (kpi,))
        else:
            add("quality.test_case_summary_unavailable", PerformanceNarrativeSection.QUALITY_VERIFICATION, "No recorded test-case pass ratio is available because there are no valid test-case denominators.", (kpi,))

        deployments = report.deployment_evidence
        add("deployment.summary", PerformanceNarrativeSection.DEPLOYMENT_EVIDENCE, f"The report records {deployments.deployment_record_count} deployment record(s) linked to assigned issues; linked deployment evidence does not establish that {employee_code} performed a deployment.", (kpi,))

        connections = report.requirement_connections
        if connections.explicit_implemented_requirement_link_count:
            keys = ", ".join(connections.explicit_implemented_requirement_keys)
            add("requirements.kpi_explicit_connection_summary", PerformanceNarrativeSection.REQUIREMENT_CONNECTIONS, f"The employee performance report records {connections.explicit_implemented_requirement_link_count} explicit implemented-requirement connection(s): {keys}.", (kpi,))

        activity = report.documented_activity
        add("activity.authored_comments", PerformanceNarrativeSection.DOCUMENTED_ACTIVITY, f"The report records {activity.authored_comment_count} comment(s) authored by {employee_code} across {activity.issues_commented_on_count} issue(s); comment authorship does not establish issue implementation or ownership.", (kpi,))

        timing = report.lifecycle_timing
        for fact_id, label, eligible, average in (
            ("timing.average_cycle_time", "cycle", timing.cycle_time_eligible_issue_count, timing.average_cycle_time_hours),
            ("timing.average_development_time", "development", timing.development_time_eligible_issue_count, timing.average_development_time_hours),
            ("timing.average_review_time", "review", timing.review_time_eligible_issue_count, timing.average_review_time_hours),
            ("timing.average_testing_time", "testing", timing.testing_time_eligible_issue_count, timing.average_testing_time_hours),
        ):
            if average is not None:
                add(fact_id, PerformanceNarrativeSection.LIFECYCLE_TIMING, f"Recorded average {label} time is {_format_number(average)} hours across {eligible} eligible issue(s); this is issue lifecycle time, not employee work time.", (kpi,))

    _add_linked_test_facts(add, context, sources)
    _add_linked_deployment_facts(add, context, sources)
    _add_traceability_facts(add, context, sources)

    limitations = _deduplicate(
        [*report.limitations, *getattr(context, "warnings", [])]
    )
    for index, limitation in enumerate(limitations, start=1):
        add(f"limitation.{index}", PerformanceNarrativeSection.LIMITATIONS, limitation, limitation=True)
    return EmployeePerformanceFactInventory(tuple(facts), tuple(limitations))


def validate_employee_performance_narrative_plan(
    plan: EmployeePerformanceNarrativePlan,
    inventory: EmployeePerformanceFactInventory,
    final_context: FormattedEvidenceContext,
) -> tuple[EmployeePerformanceNarrativeFact, ...]:
    """Fail closed unless every provider selection is final-context safe."""
    facts_by_id = {fact.fact_id: fact for fact in inventory.facts}
    selected: list[EmployeePerformanceNarrativeFact] = []
    seen: set[str] = set()
    for section in PerformanceNarrativeSection:
        for fact_id in getattr(plan, section.value):
            if fact_id in seen:
                raise EmployeePerformanceNarrativeValidationError("Duplicate employee performance fact selection")
            seen.add(fact_id)
            fact = facts_by_id.get(fact_id)
            if fact is None:
                raise EmployeePerformanceNarrativeValidationError("Unknown or unavailable employee performance fact selection")
            if fact.section is not section:
                raise EmployeePerformanceNarrativeValidationError("Employee performance fact was selected in the wrong section")
            if fact.limitation != (section is PerformanceNarrativeSection.LIMITATIONS):
                raise EmployeePerformanceNarrativeValidationError("Employee performance fact has an invalid limitation section")
            if any(source_id not in final_context.source_ids for source_id in fact.citation_ids):
                raise EmployeePerformanceNarrativeValidationError("Employee performance fact citations are unavailable from final evidence")
            selected.append(fact)
    return tuple(selected)


def render_employee_performance_narrative(
    selected_facts: tuple[EmployeePerformanceNarrativeFact, ...],
    inventory: EmployeePerformanceFactInventory,
) -> GroundedAnswer:
    """Render backend-owned factual prose and citations in fixed section order."""
    facts_by_section = {section: [] for section in PerformanceNarrativeSection}
    for fact in selected_facts:
        facts_by_section[fact.section].append(fact)

    lines: list[str] = []
    claims: list[GroundedClaim] = []
    for section in PerformanceNarrativeSection:
        lines.append(SECTION_LABELS[section])
        section_facts = facts_by_section[section]
        if section is PerformanceNarrativeSection.LIMITATIONS:
            selected_limitations = [fact.statement for fact in section_facts]
            rendered_limitations = _deduplicate([*inventory.baseline_limitations, *selected_limitations])
            if rendered_limitations:
                lines.extend(f"- {limitation}" for limitation in rendered_limitations)
            else:
                lines.append("- No additional deterministic limitations are recorded.")
            lines.append("")
            continue
        if section_facts:
            for fact in section_facts:
                lines.append(f"- {fact.statement}")
                claims.append(GroundedClaim(statement=fact.statement, source_ids=list(fact.citation_ids)))
        else:
            lines.append("- No factual statements were selected from the supplied evidence.")
        lines.append("")

    limitations = _deduplicate(
        [*inventory.baseline_limitations, *[fact.statement for fact in facts_by_section[PerformanceNarrativeSection.LIMITATIONS]]]
    )
    return GroundedAnswer(
        answer="\n".join(lines).strip(),
        claims=claims,
        limitations=limitations,
    )


def build_employee_performance_selection_prompt(
    question: str,
    inventory: EmployeePerformanceFactInventory,
) -> str:
    """Provide a closed fact inventory; the provider cannot supply prose or citations."""
    lines = [
        "QUESTION",
        "",
        question,
        "",
        "SAFE PERFORMANCE FACT INVENTORY",
        "Select only fact IDs from this inventory. Do not write factual prose, source IDs, citations, metrics, or limitations.",
    ]
    for section in PerformanceNarrativeSection:
        lines.extend(("", SECTION_LABELS[section]))
        section_facts = [fact for fact in inventory.facts if fact.section is section]
        if section_facts:
            lines.extend(f"- {fact.fact_id}" for fact in section_facts)
        else:
            lines.append("- No selectable facts.")
    lines.extend((
        "",
        "OUTPUT REQUIREMENTS",
        "Return JSON only, with exactly the fields delivery, quality_verification, deployment_evidence, requirement_connections, documented_activity, lifecycle_timing, and limitations.",
        "Every field must be a list of fact IDs from the matching inventory section. Do not repeat a fact ID. Empty lists are allowed.",
        "Required JSON shape:",
        "{",
        '  "delivery": [],',
        '  "quality_verification": [],',
        '  "deployment_evidence": [],',
        '  "requirement_connections": [],',
        '  "documented_activity": [],',
        '  "lifecycle_timing": [],',
        '  "limitations": []',
        "}",
    ))
    return "\n".join(lines)


def _add_linked_test_facts(add: Any, context: BoundedEvidenceContext, sources: list[Any]) -> None:
    sources_by_record = _sources_by_record(sources, EvidenceSourceType.TEST)
    issue_sources = _sources_by_record(sources, EvidenceSourceType.ISSUE)
    issue_keys = {item.id: item.issue_key for item in context.issues}
    kpi_source = _first_source_of_type(sources, EvidenceSourceType.KPI)
    for test in context.tests:
        source = sources_by_record.get(test.id)
        issue_source = issue_sources.get(test.issue_id)
        if source is None or issue_source is None or kpi_source is None:
            continue
        issue_key = issue_keys.get(test.issue_id) or getattr(source, "issue_key", None)
        if not issue_key:
            continue
        status = _value(test.testing_status)
        suffix = f" with recorded status {status}" if status else ""
        add(
            f"quality.linked_test.{source.source_id}",
            PerformanceNarrativeSection.QUALITY_VERIFICATION,
            f"A test record is linked to assigned issue {issue_key}{suffix}; this does not establish that the employee performed testing.",
            (kpi_source.source_id, issue_source.source_id, source.source_id),
        )


def _add_linked_deployment_facts(add: Any, context: BoundedEvidenceContext, sources: list[Any]) -> None:
    sources_by_record = _sources_by_record(sources, EvidenceSourceType.DEPLOYMENT)
    issue_sources = _sources_by_record(sources, EvidenceSourceType.ISSUE)
    issue_keys = {item.id: item.issue_key for item in context.issues}
    kpi_source = _first_source_of_type(sources, EvidenceSourceType.KPI)
    for deployment in context.deployments:
        source = sources_by_record.get(deployment.id)
        issue_source = issue_sources.get(deployment.issue_id)
        if source is None or issue_source is None or kpi_source is None:
            continue
        issue_key = issue_keys.get(deployment.issue_id) or getattr(source, "issue_key", None)
        if not issue_key:
            continue
        parts = [value for value in (_value(deployment.deployment_status), _value(deployment.environment)) if value]
        descriptor = " ".join(parts).lower() if parts else "recorded"
        add(
            f"deployment.linked_record.{source.source_id}",
            PerformanceNarrativeSection.DEPLOYMENT_EVIDENCE,
            f"A {descriptor} deployment record is linked to assigned issue {issue_key}; this does not establish that the employee performed a deployment.",
            (kpi_source.source_id, issue_source.source_id, source.source_id),
        )


def _add_traceability_facts(add: Any, context: BoundedEvidenceContext, sources: list[Any]) -> None:
    requirements_by_id = {item.id: item for item in context.requirements}
    requirement_sources = _sources_by_record(sources, EvidenceSourceType.REQUIREMENT)
    trace_sources = _sources_by_record(sources, EvidenceSourceType.TRACEABILITY)
    for trace in context.trace_links:
        requirement = requirements_by_id.get(trace.requirement_id)
        requirement_source = requirement_sources.get(trace.requirement_id)
        trace_source = trace_sources.get(trace.id)
        if requirement is None or requirement_source is None or trace_source is None:
            continue
        add(f"requirements.explicit_trace.{trace_source.source_id}", PerformanceNarrativeSection.REQUIREMENT_CONNECTIONS, f"Requirement {requirement.requirement_key} has an explicitly recorded {_value(trace.link_kind)} relationship to {_value(trace.target_label)}.", (requirement_source.source_id, trace_source.source_id))


def _first_source_of_type(sources: list[Any], source_type: EvidenceSourceType) -> Any | None:
    return next((source for source in sources if _source_type(source) == source_type.value), None)


def _sources_by_record(sources: list[Any], source_type: EvidenceSourceType) -> dict[object, Any]:
    return {source.record_id: source for source in sources if _source_type(source) == source_type.value}


def _source_type(source: Any) -> str:
    value = getattr(source, "source_type", None)
    return getattr(value, "value", value) if isinstance(getattr(value, "value", value), str) else ""


def _value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw) if raw is not None else ""


def _format_number(value: float) -> str:
    normalized = float(value)
    return str(int(normalized)) if normalized.is_integer() else f"{normalized:.1f}"


def _deduplicate(values: list[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if isinstance(value, str) and value.strip()))
