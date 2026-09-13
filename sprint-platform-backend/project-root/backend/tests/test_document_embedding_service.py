from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.core.config import settings
from app.models import DocumentStatus
from app.routers import documents
from app.schemas.document import DocumentEmbeddingResult
from app.services import document_embedding_service
from app.services.document_embedding_service import DocumentEmbeddingError
from app.services.embedding_service import EmbeddingError


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD")


def document(status: DocumentStatus = DocumentStatus.PROCESSED) -> SimpleNamespace:
    return SimpleNamespace(id=DOCUMENT_ID, project_id=PROJECT_ID, status=status)


def chunk(index: int, content: str, embedding: list[float] | None = None) -> SimpleNamespace:
    return SimpleNamespace(chunk_index=index, content=content, embedding=embedding)


class DocumentEmbeddingServiceTests(unittest.TestCase):
    def _db_with_chunks(self, chunks: list[SimpleNamespace]) -> Mock:
        db = Mock()
        db.scalars.return_value = chunks
        return db

    def test_embeds_ordered_chunks_in_one_batch_and_commits_once(self) -> None:
        chunks = [chunk(0, "first"), chunk(1, "second")]
        db = self._db_with_chunks(chunks)
        vectors = [[0.1] * 384, [0.2] * 384]
        with patch.object(
            document_embedding_service, "embed_documents", return_value=vectors
        ) as embed:
            result = document_embedding_service.embed_document_chunks(db, document())

        self.assertEqual(result, 2)
        embed.assert_called_once_with(["first", "second"])
        self.assertEqual(chunks[0].embedding, vectors[0])
        self.assertEqual(chunks[1].embedding, vectors[1])
        self.assertEqual(db.commit.call_count, 1)
        statement = db.scalars.call_args.args[0]
        self.assertIn("ORDER BY document_chunks.chunk_index", str(statement))

    def test_reembedding_replaces_existing_vectors(self) -> None:
        chunks = [chunk(0, "first", [9.0] * 384)]
        db = self._db_with_chunks(chunks)
        replacement = [[0.3] * 384]
        with patch.object(document_embedding_service, "embed_documents", return_value=replacement):
            document_embedding_service.embed_document_chunks(db, document())

        self.assertEqual(chunks[0].embedding, replacement[0])
        db.commit.assert_called_once()

    def test_missing_chunks_and_non_processed_document_are_controlled_errors(self) -> None:
        empty_db = self._db_with_chunks([])
        with self.assertRaises(DocumentEmbeddingError) as no_chunks:
            document_embedding_service.embed_document_chunks(empty_db, document())
        self.assertEqual(no_chunks.exception.status_code, 409)

        db = Mock()
        with self.assertRaises(DocumentEmbeddingError) as status_error:
            document_embedding_service.embed_document_chunks(
                db, document(DocumentStatus.UPLOADED)
            )
        self.assertEqual(status_error.exception.status_code, 409)
        db.scalars.assert_not_called()

    def test_vector_count_mismatch_and_embedding_failure_are_translated(self) -> None:
        chunks = [chunk(0, "first"), chunk(1, "second")]
        mismatch_db = self._db_with_chunks(chunks)
        with patch.object(document_embedding_service, "embed_documents", return_value=[[0.1] * 384]):
            with self.assertRaises(DocumentEmbeddingError) as mismatch:
                document_embedding_service.embed_document_chunks(mismatch_db, document())
        self.assertIn("count", mismatch.exception.detail)
        mismatch_db.commit.assert_not_called()

        failure_db = self._db_with_chunks([chunk(0, "first")])
        with patch.object(
            document_embedding_service,
            "embed_documents",
            side_effect=EmbeddingError("synthetic model failure"),
        ):
            with self.assertRaises(DocumentEmbeddingError) as failure:
                document_embedding_service.embed_document_chunks(failure_db, document())
        self.assertEqual(failure.exception.detail, "Unable to generate document embeddings")
        self.assertIsInstance(failure.exception.__cause__, EmbeddingError)

    def test_persistence_failure_rolls_back(self) -> None:
        db = self._db_with_chunks([chunk(0, "first")])
        db.commit.side_effect = RuntimeError("synthetic database failure")
        with patch.object(document_embedding_service, "embed_documents", return_value=[[0.1] * 384]):
            with self.assertRaises(DocumentEmbeddingError) as error:
                document_embedding_service.embed_document_chunks(db, document())

        self.assertEqual(error.exception.detail, "Unable to persist document embeddings")
        self.assertIsInstance(error.exception.__cause__, RuntimeError)
        db.rollback.assert_called_once()


class DocumentEmbeddingRouterTests(unittest.TestCase):
    def _db_with_document(self, source_document: SimpleNamespace) -> Mock:
        db = Mock()
        db.scalar.side_effect = [project(), source_document]
        return db

    def test_endpoint_returns_compact_result_without_vectors(self) -> None:
        source_document = document()
        db = self._db_with_document(source_document)
        with patch.object(documents, "embed_document_chunks", return_value=2) as service:
            response = documents.embed_project_document("RD", DOCUMENT_ID, db)

        service.assert_called_once_with(db, source_document)
        self.assertEqual(response.document_id, DOCUMENT_ID)
        self.assertEqual(response.project_id, PROJECT_ID)
        self.assertEqual(response.embedded_chunk_count, 2)
        self.assertEqual(response.embedding_dimension, 384)
        self.assertNotIn("embedding", DocumentEmbeddingResult.model_fields)

    def test_endpoint_rejects_non_processed_and_missing_or_cross_project_records(self) -> None:
        for document_status in (
            DocumentStatus.UPLOADED,
            DocumentStatus.PROCESSING,
            DocumentStatus.FAILED,
        ):
            with self.subTest(status=document_status):
                non_processed_db = self._db_with_document(document(document_status))
                with self.assertRaises(HTTPException) as status_error:
                    documents.embed_project_document("RD", DOCUMENT_ID, non_processed_db)
                self.assertEqual(status_error.exception.status_code, 409)

        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as project_error:
            documents.embed_project_document("RD", DOCUMENT_ID, missing_project_db)
        self.assertEqual(project_error.exception.status_code, 404)
        self.assertEqual(project_error.exception.detail, "Project not found")

        cross_project_db = Mock()
        cross_project_db.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as document_error:
            documents.embed_project_document("RD", DOCUMENT_ID, cross_project_db)
        self.assertEqual(document_error.exception.status_code, 404)
        self.assertEqual(document_error.exception.detail, "Document not found")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
