"""Pure membership validation for citations returned in a grounded answer."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.llm.evidence_context_formatter import FormattedEvidenceContext
from app.services.llm.grounded_answer import GroundedAnswer


@dataclass(frozen=True)
class CitationValidationResult:
    """Ordered citation membership outcome for one exact formatted context."""

    valid: bool
    cited_source_ids: tuple[str, ...]
    valid_source_ids: tuple[str, ...]
    invalid_source_ids: tuple[str, ...]


def validate_answer_citations(
    answer: GroundedAnswer,
    context: FormattedEvidenceContext,
) -> CitationValidationResult:
    """Check only whether answer citations were supplied in this formatted context."""
    seen: set[str] = set()
    cited_source_ids: list[str] = []
    for claim in answer.claims:
        for source_id in claim.source_ids:
            if source_id not in seen:
                seen.add(source_id)
                cited_source_ids.append(source_id)

    allowed_source_ids = set(context.source_ids)
    valid_source_ids = tuple(source_id for source_id in cited_source_ids if source_id in allowed_source_ids)
    invalid_source_ids = tuple(source_id for source_id in cited_source_ids if source_id not in allowed_source_ids)
    return CitationValidationResult(
        valid=not invalid_source_ids,
        cited_source_ids=tuple(cited_source_ids),
        valid_source_ids=valid_source_ids,
        invalid_source_ids=invalid_source_ids,
    )
