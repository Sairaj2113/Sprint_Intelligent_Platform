"""Focused no-network contracts for Phase 12E verified traceability."""

from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from app.models.requirement_trace_link import RequirementTraceLink, RequirementTraceLinkKind
from app.schemas.requirement import RequirementTraceLinkCreate
from app.services.requirement_traceability_service import (
    RequirementTraceabilityError,
    create_verified_trace_link,
)
from app.services.llm.grounding_prompt import build_grounding_system_prompt


class RequirementTraceabilityContractTests(unittest.TestCase):
    def test_exactly_one_target_and_matching_kind_are_required(self) -> None:
        verifier = uuid.uuid4()
        with self.assertRaises(ValueError):
            RequirementTraceLinkCreate(
                link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
                verified_by=verifier,
            )
        with self.assertRaises(ValueError):
            RequirementTraceLinkCreate(
                link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
                issue_id=uuid.uuid4(), test_result_id=uuid.uuid4(), verified_by=verifier,
            )
        with self.assertRaises(ValueError):
            RequirementTraceLinkCreate(
                link_kind=RequirementTraceLinkKind.VERIFIED_BY_TEST,
                issue_id=uuid.uuid4(), verified_by=verifier,
            )

    def test_database_model_has_exactly_one_target_constraint(self) -> None:
        constraints = {constraint.name for constraint in RequirementTraceLink.__table__.constraints}
        self.assertIn("ck_requirement_trace_links_exactly_one_target", constraints)

    def test_cross_project_issue_target_is_rejected(self) -> None:
        project = SimpleNamespace(id=uuid.uuid4())
        requirement = SimpleNamespace(id=uuid.uuid4())
        verifier = SimpleNamespace(id=uuid.uuid4())
        db = Mock()
        # project, requirement, verifier, project-member check, then issue scoped to project
        db.scalar.side_effect = [project, requirement, verifier, uuid.uuid4(), None]
        with self.assertRaises(RequirementTraceabilityError) as error:
            create_verified_trace_link(
                db, "BLI", "BLI-REQ-001",
                link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
                issue_id=uuid.uuid4(), test_result_id=None, deployment_id=None,
                verified_by_id=verifier.id,
            )
        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Issue target not found")

    def test_no_transitive_target_is_created(self) -> None:
        """An issue link has only issue_id; it cannot imply a test or deployment link."""
        link = RequirementTraceLink(
            project_id=uuid.uuid4(), requirement_id=uuid.uuid4(),
            link_kind=RequirementTraceLinkKind.IMPLEMENTED_BY_ISSUE,
            issue_id=uuid.uuid4(), verified_by_id=uuid.uuid4(),
        )
        self.assertIsNotNone(link.issue_id)
        self.assertIsNone(link.test_result_id)
        self.assertIsNone(link.deployment_id)

    def test_grounding_preserves_traceability_and_attribution_boundary(self) -> None:
        prompt = build_grounding_system_prompt().casefold()
        self.assertIn("verified traceability record may establish only its declared", prompt)
        self.assertIn("does not establish employee ownership", prompt)
        self.assertIn("do not by themselves establish formal", prompt)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
