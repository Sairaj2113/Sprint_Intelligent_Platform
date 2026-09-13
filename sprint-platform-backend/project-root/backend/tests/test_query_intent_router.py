from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.routers import query_intent
from app.schemas.query_intent import QueryIntentRequest, QueryIntentResponse
from app.services.query_intent_service import QueryIntent


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class QueryIntentRouterTests(unittest.TestCase):
    def test_valid_project_returns_classification_schema_without_retrieval(self) -> None:
        db = Mock()
        db.scalar.return_value = SimpleNamespace(id=PROJECT_ID, project_key="BLI")
        request = QueryIntentRequest(
            query="What did Sairaj contribute toward the model requirements?"
        )
        with patch("app.services.retrieval_service.search_project_documents") as retrieval:
            response = query_intent.classify_project_query("BLI", request, db)

        self.assertIsInstance(response, QueryIntentResponse)
        self.assertEqual(response.intent, QueryIntent.HYBRID)
        self.assertEqual(response.employee_reference, "Sairaj")
        self.assertTrue(response.needs_structured_evidence)
        self.assertTrue(response.needs_document_evidence)
        retrieval.assert_not_called()

    def test_missing_project_returns_404(self) -> None:
        db = Mock()
        db.scalar.return_value = None
        with self.assertRaises(HTTPException) as error:
            query_intent.classify_project_query(
                "MISSING", QueryIntentRequest(query="requirements"), db
            )

        self.assertEqual(error.exception.status_code, 404)
        self.assertEqual(error.exception.detail, "Project not found")

    def test_blank_query_is_rejected_with_controlled_validation_error(self) -> None:
        db = Mock()
        db.scalar.return_value = SimpleNamespace(id=PROJECT_ID, project_key="BLI")
        with self.assertRaises(HTTPException) as error:
            query_intent.classify_project_query("BLI", QueryIntentRequest(query="  "), db)

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail, "Query must not be blank")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
