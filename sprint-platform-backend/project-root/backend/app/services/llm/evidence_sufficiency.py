"""Deterministic structural evidence-condition assessment for grounded answers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.llm.citation_validator import CitationValidationResult
from app.services.llm.evidence_context_formatter import FormattedEvidenceContext
from app.services.llm.grounded_answer import GroundedAnswer


class EvidenceSufficiencyStatus(str, Enum):
    """Deterministic pipeline conditions, not semantic evidence-quality judgments."""

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    LIMITED = "LIMITED"
    INVALID_CITATIONS = "INVALID_CITATIONS"


@dataclass(frozen=True)
class EvidenceSufficiencyResult:
    """Immutable structural assessment for future orchestration decisions."""

    status: EvidenceSufficiencyStatus
    can_proceed: bool
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]


def assess_evidence_sufficiency(
    answer: GroundedAnswer,
    context: FormattedEvidenceContext,
    citation_validation: CitationValidationResult,
) -> EvidenceSufficiencyResult:
    """Assess only deterministic grounding conditions; semantic support is not proven."""
    limitations = tuple(answer.limitations)
    if not citation_validation.valid:
        return EvidenceSufficiencyResult(
            status=EvidenceSufficiencyStatus.INVALID_CITATIONS,
            can_proceed=False,
            reasons=("One or more answer citations were not present in the supplied evidence context.",),
            limitations=limitations,
        )

    if not context.source_ids:
        return EvidenceSufficiencyResult(
            status=EvidenceSufficiencyStatus.INSUFFICIENT,
            can_proceed=False,
            reasons=("No evidence sources were supplied for grounded project-specific claims.",),
            limitations=limitations,
        )

    reasons: list[str] = []
    if not answer.claims:
        reasons.append("The grounded answer contains no evidence-backed factual claims.")
    if context.truncated:
        reasons.append("The supplied evidence context was truncated.")
    if answer.limitations:
        reasons.append("The grounded answer reports evidence limitations.")
    if reasons:
        return EvidenceSufficiencyResult(
            status=EvidenceSufficiencyStatus.LIMITED,
            can_proceed=True,
            reasons=tuple(reasons),
            limitations=limitations,
        )

    return EvidenceSufficiencyResult(
        status=EvidenceSufficiencyStatus.SUFFICIENT,
        can_proceed=True,
        reasons=(),
        limitations=limitations,
    )
