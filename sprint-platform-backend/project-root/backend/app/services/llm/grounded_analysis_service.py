"""Application orchestration for one evidence-grounded LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.core.config import settings
from app.services.llm.base import LLMGenerationRequest, LLMUsage
from app.services.llm.citation_validator import (
    CitationValidationResult,
    validate_answer_citations,
)
from app.services.llm.evidence_context_formatter import (
    FormattedEvidenceContext,
    format_evidence_context,
)
from app.services.llm.evidence_sufficiency import (
    EvidenceSufficiencyResult,
    EvidenceSufficiencyStatus,
    assess_evidence_sufficiency,
)
from app.services.llm.employee_performance_narrative import (
    EmployeePerformanceNarrativePlan,
    EmployeePerformanceNarrativeValidationError,
    build_employee_performance_fact_inventory,
    build_employee_performance_selection_prompt,
    has_employee_performance_evidence,
    render_employee_performance_narrative,
    validate_employee_performance_narrative_plan,
)
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.llm.grounding_prompt import build_grounding_system_prompt
from app.services.llm.input_budget_service import (
    GroundedInputBudget,
    GroundedInputBudgetError,
    estimate_input_tokens,
    trim_context_to_input_budget,
)
from app.services.llm.llm_service import LLMService

if TYPE_CHECKING:
    from app.services.evidence_context_service import BoundedEvidenceContext


_NO_EVIDENCE_REASON = "No evidence sources were supplied for grounded project-specific claims."


class GroundedAnalysisError(Exception):
    """Controlled error raised while preparing a grounded analysis."""

    def __init__(self, detail: str, *, status_code: int = 422) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class GroundedAnalysisOutputError(GroundedAnalysisError):
    """Controlled error for a provider response that violates the answer contract."""

    def __init__(self) -> None:
        super().__init__("Unable to produce a valid grounded analysis", status_code=502)


@dataclass(frozen=True)
class GroundedAnalysisResult:
    """One parsed grounded answer and its deterministic evidence checks."""

    question: str
    answer: GroundedAnswer | None
    citation_validation: CitationValidationResult | None
    evidence_sufficiency: EvidenceSufficiencyResult
    provider: str | None
    model: str | None
    fallback_used: bool | None
    usage: LLMUsage | None
    source_ids: tuple[str, ...]


def analyze_grounded_question(
    question: str,
    bounded_context: BoundedEvidenceContext,
    llm_service: LLMService,
) -> GroundedAnalysisResult:
    """Generate and validate exactly one structured grounded answer when evidence exists."""
    _validate_question(question)
    system_prompt = build_grounding_system_prompt()
    bounded_context, formatted_context = _prepare_budgeted_context(
        question,
        bounded_context,
        system_prompt,
    )
    if not formatted_context.source_ids:
        return _empty_evidence_result(
            question,
            source_ids=formatted_context.source_ids,
            limitations=_context_warnings(bounded_context),
        )

    if has_employee_performance_evidence(bounded_context):
        inventory = build_employee_performance_fact_inventory(bounded_context)
        generation = llm_service.generate(
            LLMGenerationRequest(
                system_prompt=system_prompt,
                user_prompt=build_employee_performance_selection_prompt(question, inventory),
                temperature=0,
            )
        )
        try:
            plan = EmployeePerformanceNarrativePlan.model_validate_json(generation.content)
            selected_facts = validate_employee_performance_narrative_plan(
                plan,
                inventory,
                formatted_context,
            )
            answer = render_employee_performance_narrative(selected_facts, inventory)
        except (
            TypeError,
            ValueError,
            ValidationError,
            EmployeePerformanceNarrativeValidationError,
        ) as error:
            raise GroundedAnalysisOutputError() from error
    else:
        generation = llm_service.generate(
            LLMGenerationRequest(
                system_prompt=system_prompt,
                user_prompt=_build_user_prompt(question, formatted_context),
                temperature=0,
            )
        )
        try:
            answer = GroundedAnswer.model_validate_json(generation.content)
        except (TypeError, ValueError, ValidationError) as error:
            raise GroundedAnalysisOutputError() from error

    citation_validation = validate_answer_citations(answer, formatted_context)
    evidence_sufficiency = assess_evidence_sufficiency(
        answer,
        formatted_context,
        citation_validation,
    )
    return GroundedAnalysisResult(
        question=question,
        answer=answer,
        citation_validation=citation_validation,
        evidence_sufficiency=evidence_sufficiency,
        provider=generation.provider,
        model=generation.model,
        fallback_used=generation.fallback_used,
        usage=generation.usage,
        source_ids=formatted_context.source_ids,
    )


def _prepare_budgeted_context(
    question: str,
    context: BoundedEvidenceContext,
    system_prompt: str,
) -> tuple[BoundedEvidenceContext, FormattedEvidenceContext]:
    """Apply pure pre-provider evidence budgeting and retain its final formatter value."""
    budget = GroundedInputBudget(
        effective_envelope_tokens=settings.GROUNDED_INPUT_EFFECTIVE_ENVELOPE_TOKENS,
        safety_margin_tokens=settings.GROUNDED_INPUT_SAFETY_MARGIN_TOKENS,
    )
    rendered: dict[int, FormattedEvidenceContext] = {}

    def measure(candidate: BoundedEvidenceContext) -> int:
        formatted = format_evidence_context(candidate)
        rendered[id(candidate)] = formatted
        return estimate_input_tokens(system_prompt, _build_user_prompt(question, formatted))

    try:
        budgeted_context = trim_context_to_input_budget(
            context,
            budget=budget,
            measure_context=measure,
        )
    except GroundedInputBudgetError as error:
        raise GroundedAnalysisError(error.detail) from error
    formatted_context = rendered.get(id(budgeted_context)) or format_evidence_context(budgeted_context)
    return budgeted_context, formatted_context


def _validate_question(question: str) -> None:
    if not isinstance(question, str) or not question.strip():
        raise GroundedAnalysisError("Question must not be blank")


def _context_warnings(context: object) -> tuple[str, ...]:
    warnings = getattr(context, "warnings", ())
    if not isinstance(warnings, (list, tuple)):
        return ()
    return tuple(warning for warning in warnings if isinstance(warning, str) and warning.strip())


def _empty_evidence_result(
    question: str,
    *,
    source_ids: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> GroundedAnalysisResult:
    return GroundedAnalysisResult(
        question=question,
        answer=None,
        citation_validation=None,
        evidence_sufficiency=EvidenceSufficiencyResult(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            can_proceed=False,
            reasons=(_NO_EVIDENCE_REASON,),
            limitations=limitations,
        ),
        provider=None,
        model=None,
        fallback_used=None,
        usage=None,
        source_ids=source_ids,
    )


def _build_user_prompt(question: str, context: FormattedEvidenceContext) -> str:
    """Keep instructions and untrusted evidence in stable, separate user-prompt sections."""
    return "\n\n".join(
        (
            "QUESTION\n\n" + question,
            "EVIDENCE\n\n" + context.text,
            "OUTPUT REQUIREMENTS\n\n" + _build_output_requirements(context.source_ids),
        )
    )


def _build_output_requirements(source_ids: tuple[str, ...]) -> str:
    allowed = ", ".join(source_ids)
    return "\n".join(
        (
            "Return JSON only. Do not use Markdown fences or include prose outside the JSON object.",
            "Use exactly the top-level fields answer, claims, and limitations.",
            "Each claim must use exactly the fields statement and source_ids.",
            "Zero claims are allowed when the supplied evidence cannot support a factual claim.",
            "Project-specific factual claims require supporting source_ids.",
            "The supplied source IDs form a CLOSED, NON-SEQUENTIAL ALLOW-LIST.",
            "Cite only source IDs appearing verbatim in the supplied source registry.",
            "Copy every cited source ID exactly from that registry.",
            "Never create, increment, infer, or range-expand a source ID.",
            "The numeric portion of a source ID has no semantic meaning; a highest listed ID does not imply another source exists.",
            "If no supplied source supports a statement, do not cite an invented source; prefer omitting the unsupported claim.",
            f"SUPPLIED SOURCE REGISTRY (closed allow-list): {allowed}.",
            "Limitations should state evidence gaps where appropriate.",
            "Required JSON shape:",
            "{",
            '  "answer": "string",',
            '  "claims": [],',
            '  "limitations": ["string"]',
            "}",
        )
    )
