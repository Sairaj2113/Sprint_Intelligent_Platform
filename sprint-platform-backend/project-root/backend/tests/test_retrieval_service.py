from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import DocumentType
from app.services import retrieval_service
from app.services.embedding_service import EmbeddingError
from app.services.retrieval_service import SemanticRetrievalError


BLI_PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
RD_PROJECT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def chunk(index: int, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        chunk_index=index,
        content=content,
        page_number=4,
        section_title="Architecture",
        metadata_json={"source_type": "pdf"},
    )


def document(document_type: DocumentType = DocumentType.PRD) -> SimpleNamespace:
    return SimpleNamespace(id=DOCUMENT_ID, title="Platform PRD", document_type=document_type)


class RetrievalServiceTests(unittest.TestCase):
    def _db_with_rows(self, rows: list[tuple[SimpleNamespace, SimpleNamespace, float]]) -> Mock:
        db = Mock()
        db.execute.return_value.all.return_value = rows
        return db

    def test_query_is_embedded_once_and_results_preserve_database_distance_order(self) -> None:
        first, second = chunk(0, "first result"), chunk(1, "second result")
        db = self._db_with_rows([(first, document(), 0.12), (second, document(), 0.46)])
        with patch.object(retrieval_service, "embed_query", return_value=[0.1] * 384) as embed:
            results = retrieval_service.search_project_documents(
                db, BLI_PROJECT_ID, "architecture", top_k=2
            )

        embed.assert_called_once_with("architecture")
        self.assertEqual([result.chunk_id for result in results], [first.id, second.id])
        self.assertEqual([result.distance for result in results], [0.12, 0.46])
        self.assertTrue(all(isinstance(result.distance, float) for result in results))
        self.assertEqual(results[0].document_title, "Platform PRD")
        self.assertEqual(results[0].document_type, DocumentType.PRD)
        self.assertEqual(results[0].metadata_json, {"source_type": "pdf"})

        statement = db.execute.call_args.args[0]
        compiled = statement.compile()
        self.assertIn("<=>", str(statement))
        self.assertIn("document_chunks.project_id", str(statement))
        self.assertIn("IS NOT NULL", str(statement))
        self.assertIn(BLI_PROJECT_ID, compiled.params.values())
        self.assertEqual(statement._limit_clause.value, 2)

    def test_document_type_filter_is_optional_and_is_applied_by_database_query(self) -> None:
        filtered_db = self._db_with_rows([])
        with patch.object(retrieval_service, "embed_query", return_value=[0.1] * 384):
            retrieval_service.search_project_documents(
                filtered_db,
                BLI_PROJECT_ID,
                "requirements",
                document_types=[DocumentType.PRD, DocumentType.TRD],
            )
        filtered_statement = filtered_db.execute.call_args.args[0]
        self.assertIn("documents.document_type IN", str(filtered_statement))
        self.assertIn(
            [DocumentType.PRD, DocumentType.TRD],
            filtered_statement.compile().params.values(),
        )

        all_types_db = self._db_with_rows([])
        with patch.object(retrieval_service, "embed_query", return_value=[0.1] * 384):
            results = retrieval_service.search_project_documents(
                all_types_db, BLI_PROJECT_ID, "requirements"
            )
        self.assertEqual(results, [])
        self.assertNotIn("documents.document_type IN", str(all_types_db.execute.call_args.args[0]))

    def test_project_scope_is_bound_directly_to_document_chunks(self) -> None:
        db = self._db_with_rows([])
        with patch.object(retrieval_service, "embed_query", return_value=[0.1] * 384):
            retrieval_service.search_project_documents(db, BLI_PROJECT_ID, "ownership")

        statement = db.execute.call_args.args[0]
        self.assertIn("document_chunks.project_id", str(statement))
        self.assertIn(BLI_PROJECT_ID, statement.compile().params.values())
        self.assertNotIn(RD_PROJECT_ID, statement.compile().params.values())

    def test_embedding_and_database_failures_are_translated(self) -> None:
        db = Mock()
        with patch.object(
            retrieval_service, "embed_query", side_effect=EmbeddingError("synthetic model failure")
        ):
            with self.assertRaises(SemanticRetrievalError) as embedding_error:
                retrieval_service.search_project_documents(db, BLI_PROJECT_ID, "architecture")
        self.assertIsInstance(embedding_error.exception.__cause__, EmbeddingError)
        db.execute.assert_not_called()

        db.execute.side_effect = RuntimeError("synthetic database failure")
        with patch.object(retrieval_service, "embed_query", return_value=[0.1] * 384):
            with self.assertRaises(SemanticRetrievalError) as database_error:
                retrieval_service.search_project_documents(db, BLI_PROJECT_ID, "architecture")
        self.assertIsInstance(database_error.exception.__cause__, RuntimeError)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
