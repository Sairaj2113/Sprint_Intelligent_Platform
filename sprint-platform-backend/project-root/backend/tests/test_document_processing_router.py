from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.models import DocumentChunk, DocumentStatus
from app.routers import documents
from app.services.document_chunking_service import ChunkData
from app.services.document_extraction_service import ExtractedBlock, NoExtractableTextError


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD")


def document(status: DocumentStatus = DocumentStatus.UPLOADED, suffix: str = ".pdf") -> SimpleNamespace:
    return SimpleNamespace(
        id=DOCUMENT_ID,
        project_id=PROJECT_ID,
        status=status,
        processed_at=None,
        storage_path=f"RD/{DOCUMENT_ID}/requirements{suffix}",
        original_filename=f"requirements{suffix}",
    )


def extracted_block(source_type: str = "pdf") -> ExtractedBlock:
    return ExtractedBlock(
        text="RetailDialogue requirements",
        page_number=1 if source_type == "pdf" else None,
        section_title="Architecture" if source_type == "docx" else None,
        metadata={"source_type": source_type},
    )


def chunk(index: int = 0) -> ChunkData:
    return ChunkData(
        chunk_index=index,
        content=f"chunk {index}",
        token_count=None,
        page_number=1,
        section_title=None,
        metadata_json={"source_type": "pdf", "page_number": 1},
    )


class DocumentProcessingRouterTests(unittest.TestCase):
    def _db_with_document(self, source_document: SimpleNamespace) -> Mock:
        db = Mock()
        db.scalar.side_effect = [project(), source_document]
        return db

    def _process(self, db: Mock):
        return documents.process_project_document("RD", DOCUMENT_ID, db)

    def test_uploaded_pdf_processes_chunks_and_keeps_embeddings_null(self) -> None:
        source_document = document()
        db = self._db_with_document(source_document)
        with patch.object(documents, "extract_document", return_value=[extracted_block()]), patch.object(
            documents, "chunk_blocks", return_value=[chunk(), chunk(1)]
        ):
            response = self._process(db)

        persisted_chunks = [call.args[0] for call in db.add.call_args_list]
        self.assertEqual(response.status, DocumentStatus.PROCESSED)
        self.assertEqual(response.chunk_count, 2)
        self.assertIsNotNone(response.processed_at)
        self.assertEqual(source_document.status, DocumentStatus.PROCESSED)
        self.assertEqual(db.commit.call_count, 2)
        self.assertEqual(len(persisted_chunks), 2)
        self.assertTrue(all(isinstance(item, DocumentChunk) for item in persisted_chunks))
        self.assertTrue(all(item.embedding is None for item in persisted_chunks))

    def test_uploaded_docx_processes_successfully(self) -> None:
        db = self._db_with_document(document(suffix=".docx"))
        with patch.object(documents, "extract_document", return_value=[extracted_block("docx")]), patch.object(
            documents, "chunk_blocks", return_value=[chunk()]
        ):
            response = self._process(db)

        self.assertEqual(response.status, DocumentStatus.PROCESSED)
        self.assertEqual(response.chunk_count, 1)

    def test_missing_project_cross_project_and_conflicting_statuses_are_rejected(self) -> None:
        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as project_error:
            self._process(missing_project_db)
        self.assertEqual(project_error.exception.detail, "Project not found")

        missing_document_db = Mock()
        missing_document_db.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as document_error:
            self._process(missing_document_db)
        self.assertEqual(document_error.exception.detail, "Document not found")

        for source_document, expected_detail in (
            (document(DocumentStatus.PROCESSING), "Document is already being processed"),
            (document(DocumentStatus.PROCESSED), "Document has already been processed"),
        ):
            with self.subTest(status=source_document.status):
                db = self._db_with_document(source_document)
                with self.assertRaises(HTTPException) as status_error:
                    self._process(db)
                self.assertEqual(status_error.exception.status_code, 409)
                self.assertEqual(status_error.exception.detail, expected_detail)

    def test_failed_document_retry_deletes_stale_chunks_before_processing(self) -> None:
        source_document = document(DocumentStatus.FAILED)
        db = self._db_with_document(source_document)
        with patch.object(documents, "extract_document", return_value=[extracted_block()]), patch.object(
            documents, "chunk_blocks", return_value=[chunk()]
        ):
            response = self._process(db)

        self.assertEqual(response.status, DocumentStatus.PROCESSED)
        self.assertEqual(db.execute.call_count, 1)
        self.assertEqual(db.commit.call_count, 2)

    def test_empty_extraction_marks_document_failed_with_controlled_error(self) -> None:
        source_document = document()
        db = self._db_with_document(source_document)
        with patch.object(documents, "extract_document", side_effect=NoExtractableTextError()):
            with self.assertRaises(HTTPException) as error:
                self._process(db)

        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(error.exception.detail, "No extractable text found in document")
        self.assertEqual(source_document.status, DocumentStatus.FAILED)
        self.assertEqual(db.commit.call_count, 2)

    def test_persistence_failure_rolls_back_partial_chunk_set_and_marks_failed(self) -> None:
        source_document = document()
        db = self._db_with_document(source_document)
        db.add.side_effect = [None, RuntimeError("synthetic persistence failure")]
        with patch.object(documents, "extract_document", return_value=[extracted_block()]), patch.object(
            documents, "chunk_blocks", return_value=[chunk(), chunk(1)]
        ):
            with self.assertRaises(HTTPException) as error:
                self._process(db)

        self.assertEqual(error.exception.status_code, 500)
        self.assertEqual(error.exception.detail, "Unable to persist document chunks")
        self.assertEqual(source_document.status, DocumentStatus.FAILED)
        self.assertGreaterEqual(db.rollback.call_count, 1)

    def test_list_chunks_orders_by_chunk_index(self) -> None:
        source_document = document(DocumentStatus.PROCESSED)
        db = self._db_with_document(source_document)
        db.scalars.return_value = [SimpleNamespace(chunk_index=0), SimpleNamespace(chunk_index=1)]

        response = documents.list_project_document_chunks("RD", DOCUMENT_ID, db)

        self.assertEqual([item.chunk_index for item in response], [0, 1])
        statement = db.scalars.call_args.args[0]
        self.assertIn("ORDER BY document_chunks.chunk_index", str(statement))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
