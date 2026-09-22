"""Application orchestration for one evidence-grounded LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import ValidationError

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
from app.services.llm.grounded_answer import GroundedAnswer
from app.services.llm.grounding_prompt import build_grounding_system_prompt
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


def analyze_grounded_question(
    question: str,
    bounded_context: BoundedEvidenceContext,
    llm_service: LLMService,
) -> GroundedAnalysisResult:
    """Generate and validate exactly one structured grounded answer when evidence exists."""
    _validate_question(question)
    formatted_context = format_evidence_context(bounded_context)
    if not formatted_context.source_ids:
        return _empty_evidence_result(question)

    generation = llm_service.generate(
        LLMGenerationRequest(
            system_prompt=build_grounding_system_prompt(),
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
    )


def _validate_question(question: str) -> None:
    if not isinstance(question, str) or not question.strip():
        raise GroundedAnalysisError("Question must not be blank")


def _empty_evidence_result(question: str) -> GroundedAnalysisResult:
    return GroundedAnalysisResult(
        question=question,
        answer=None,
        citation_validation=None,
        evidence_sufficiency=EvidenceSufficiencyResult(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            can_proceed=False,
            reasons=(_NO_EVIDENCE_REASON,),
            limitations=(),
        ),
        provider=None,
        model=None,
        fallback_used=None,
        usage=None,
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
            f"Use only these supplied source IDs: {allowed}.",
            "Limitations should state evidence gaps where appropriate.",
            "Required JSON shape:",
            "{",
            '  "answer": "string",',
            '  "claims": [{"statement": "string", "source_ids": ["ISSUE-1"]}],',
            '  "limitations": ["string"]',
            "}",
        )
    )
