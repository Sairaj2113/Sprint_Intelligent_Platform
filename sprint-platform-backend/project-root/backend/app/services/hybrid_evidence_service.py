"""Deterministic orchestration of existing structured and document evidence."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import DocumentType
from app.services.document_evidence_service import (
    DocumentEvidenceError,
    DocumentEvidencePackage,
    build_document_evidence_from_intent,
)
from app.services.query_intent_service import (
    QueryIntent,
    QueryIntentError,
    classify_query_intent,
)
from app.services.structured_evidence_service import (
    StructuredEvidenceError,
    StructuredEvidencePackage,
    build_structured_evidence,
)


class HybridEvidenceError(Exception):
    """Controlled error raised while composing existing evidence packages."""

    def __init__(self, detail: str, *, status_code: int = 500) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class HybridEvidencePackage:
    query: str
    project_key: str
    intent: QueryIntent
    needs_structured_evidence: bool
    needs_document_evidence: bool
    employee_reference: str | None
    sprint_reference: str | None
    requested_document_types: list[DocumentType]
    structured_evidence: StructuredEvidencePackage | None
    document_evidence: DocumentEvidencePackage | None
    warnings: list[str]


def _deduplicate_warnings(*warning_groups: list[str]) -> list[str]:
    warnings: list[str] = []
    for group in warning_groups:
        for warning in group:
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def build_hybrid_evidence(
    db: Session,
    project_key: str,
    query: str,
    *,
    top_k: int = 5,
) -> HybridEvidencePackage:
    """Classify once, invoke only required existing evidence branches, and merge facts."""
    try:
        intent_result = classify_query_intent(query)
    except QueryIntentError as error:
        raise HybridEvidenceError(error.args[0], status_code=422) from error
    except Exception as error:
        raise HybridEvidenceError("Unable to classify intelligence query") from error

    structured_evidence: StructuredEvidencePackage | None = None
    document_evidence: DocumentEvidencePackage | None = None
    try:
        if intent_result.needs_structured_evidence:
            structured_evidence = build_structured_evidence(
                db,
                project_key,
                employee_reference=intent_result.employee_reference,
                sprint_reference=intent_result.sprint_reference,
            )
        if intent_result.needs_document_evidence:
            document_evidence = build_document_evidence_from_intent(
                db,
                project_key,
                intent_result,
                top_k=top_k,
            )
    except StructuredEvidenceError as error:
        raise HybridEvidenceError(error.detail, status_code=error.status_code) from error
    except DocumentEvidenceError as error:
        raise HybridEvidenceError(error.detail, status_code=error.status_code) from error
    except HybridEvidenceError:
        raise
    except Exception as error:
        raise HybridEvidenceError("Unable to build hybrid evidence") from error

    return HybridEvidencePackage(
        query=intent_result.query,
        project_key=project_key,
        intent=intent_result.intent,
        needs_structured_evidence=intent_result.needs_structured_evidence,
        needs_document_evidence=intent_result.needs_document_evidence,
        employee_reference=intent_result.employee_reference,
        sprint_reference=intent_result.sprint_reference,
        requested_document_types=intent_result.document_types,
        structured_evidence=structured_evidence,
        document_evidence=document_evidence,
        warnings=_deduplicate_warnings(
            structured_evidence.warnings if structured_evidence is not None else [],
            document_evidence.warnings if document_evidence is not None else [],
        ),
    )
