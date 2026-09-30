"""Provider-neutral deterministic budgeting for a grounded-analysis input."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

from app.services.evidence_context_service import rebuild_bounded_evidence_context

if TYPE_CHECKING:
    from app.services.evidence_context_service import BoundedEvidenceContext


# A 30,496-byte measured Groq prompt used 7,627 input tokens: approximately
# 4.0 bytes/token.  3.5 bytes/token intentionally overestimates that measured
# prompt by about 14%, without relying on an SDK tokenizer or model download.
ESTIMATED_BYTES_PER_TOKEN_NUMERATOR = 7
ESTIMATED_BYTES_PER_TOKEN_DENOMINATOR = 2
# Covers chat-message serialization and request framing.  The measured SDK
# request was 575 bytes larger than concatenated system/user prompt text.
REQUEST_ENVELOPE_OVERHEAD_BYTES = 1024


class GroundedInputBudgetError(Exception):
    """A controlled error for a request that cannot fit before generation."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class GroundedInputBudget:
    """Configurable effective input envelope and reserved safety margin."""

    effective_envelope_tokens: int
    safety_margin_tokens: int

    def __post_init__(self) -> None:
        if not isinstance(self.effective_envelope_tokens, int) or self.effective_envelope_tokens < 1:
            raise GroundedInputBudgetError("Grounded input envelope must be a positive integer")
        if not isinstance(self.safety_margin_tokens, int) or not 0 <= self.safety_margin_tokens < self.effective_envelope_tokens:
            raise GroundedInputBudgetError("Grounded input safety margin must be smaller than the envelope")

    @property
    def max_estimated_input_tokens(self) -> int:
        return self.effective_envelope_tokens - self.safety_margin_tokens


def estimate_input_tokens(system_prompt: str, user_prompt: str) -> int:
    """Estimate input deterministically without provider-specific tokenization.

    This is deliberately a conservative size estimate, not reported provider
    usage and not an exact token count for any one model.
    """
    payload_bytes = (
        len(system_prompt.encode("utf-8"))
        + len(user_prompt.encode("utf-8"))
        + REQUEST_ENVELOPE_OVERHEAD_BYTES
    )
    return ceil(payload_bytes * ESTIMATED_BYTES_PER_TOKEN_DENOMINATOR / ESTIMATED_BYTES_PER_TOKEN_NUMERATOR)


def trim_context_to_input_budget(
    context: BoundedEvidenceContext,
    *,
    budget: GroundedInputBudget,
    measure_context: Callable[[BoundedEvidenceContext], int],
) -> BoundedEvidenceContext:
    """Trim whole tail records until a rendered prompt fits the input budget.

    Each category retains an ordered prefix.  This preserves structured
    evidence ordering and semantic document ranking while never slicing an
    evidence record or inventing/reassigning source labels.
    """
    current = context
    current_size = measure_context(current)
    while current_size > budget.max_estimated_input_tokens:
        candidates: list[tuple[int, int, BoundedEvidenceContext]] = []
        # Candidate lists are always prefix-preserving.  The numeric priority
        # is only a deterministic tie breaker; it never reorders retained data.
        for priority, category in enumerate(
            ("issues", "tests", "deployments", "comments", "documents", "trace_links", "requirements")
        ):
            values = getattr(current, category)
            if not values:
                continue
            replacement = {name: list(getattr(current, name)) for name in (
                "issues", "tests", "deployments", "comments", "documents", "requirements", "trace_links"
            )}
            replacement[category] = replacement[category][:-1]
            # A relationship has no usable provenance without its persisted requirement.
            # Removing a requirement therefore removes every one of its trace links;
            # removing a trace link never invents or renumbers any source.
            if category == "requirements":
                retained_ids = {item.id for item in replacement["requirements"]}
                replacement["trace_links"] = [
                    item for item in replacement["trace_links"]
                    if item.requirement_id in retained_ids
                ]
            candidate = rebuild_bounded_evidence_context(
                current,
                issues=replacement["issues"],
                tests=replacement["tests"],
                deployments=replacement["deployments"],
                comments=replacement["comments"],
                documents=replacement["documents"],
                requirements=replacement["requirements"],
                trace_links=replacement["trace_links"],
                input_budget_truncated=True,
            )
            candidate_size = measure_context(candidate)
            candidates.append((current_size - candidate_size, priority, candidate))

        if not candidates:
            raise GroundedInputBudgetError(
                "Question is too large for the configured grounded-analysis input budget"
            )

        # Prefer the candidate with the greatest exact rendered-size reduction;
        # ties use the stable category order above.
        _, _, current = max(candidates, key=lambda item: (item[0], item[1]))
        current_size = measure_context(current)
    return current
