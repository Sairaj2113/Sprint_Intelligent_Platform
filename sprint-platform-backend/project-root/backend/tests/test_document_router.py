from __future__ import annotations

import asyncio
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.models import Document, DocumentChunk, DocumentStatus, DocumentType
from app.routers import documents


PROJECT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOCUMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def project() -> SimpleNamespace:
    return SimpleNamespace(id=PROJECT_ID, project_key="RD", name="RetailDialogue")


def upload_file(filename: str, content: bytes, mime_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": mime_type}),
    )


class DocumentRouterTests(unittest.TestCase):
    def _upload(self, db: Mock, file: UploadFile, title: str = "RetailDialogue PRD") -> Document:
        return asyncio.run(
            documents.upload_project_document(
                "RD", DocumentType.PRD, title, file, db
            )
        )

    def test_valid_pdf_upload_creates_uploaded_document_without_chunks(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        db.refresh.side_effect = lambda document: setattr(
            document, "uploaded_at", datetime.now(timezone.utc)
        )
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            documents.settings, "DOCUMENT_STORAGE_ROOT", Path(temp_directory)
        ):
            document = self._upload(
                db,
                upload_file("RetailDialogue_PRD.pdf", b"pdf", "application/pdf"),
            )

            self.assertEqual(document.status, DocumentStatus.UPLOADED)
            self.assertIsNone(document.processed_at)
            self.assertEqual(document.original_filename, "RetailDialogue_PRD.pdf")
            self.assertEqual(document.file_size_bytes, 3)
            self.assertEqual(db.add.call_count, 1)
            self.assertIsInstance(db.add.call_args.args[0], Document)
            self.assertNotIsInstance(db.add.call_args.args[0], DocumentChunk)
            self.assertEqual(db.commit.call_count, 1)

    def test_valid_docx_upload_is_accepted(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        db.refresh.side_effect = lambda document: setattr(
            document, "uploaded_at", datetime.now(timezone.utc)
        )
        docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            documents.settings, "DOCUMENT_STORAGE_ROOT", Path(temp_directory)
        ):
            document = self._upload(db, upload_file("design.docx", b"docx", docx_mime))

            self.assertEqual(document.mime_type, docx_mime)

    def test_invalid_project_and_blank_title_are_rejected(self) -> None:
        missing_project_db = Mock()
        missing_project_db.scalar.return_value = None
        with self.assertRaises(HTTPException) as project_error:
            self._upload(
                missing_project_db,
                upload_file("requirements.pdf", b"pdf", "application/pdf"),
            )
        self.assertEqual(project_error.exception.status_code, 404)
        self.assertEqual(project_error.exception.detail, "Project not found")

        blank_title_db = Mock()
        blank_title_db.scalar.return_value = project()
        with self.assertRaises(HTTPException) as title_error:
            self._upload(
                blank_title_db,
                upload_file("requirements.pdf", b"pdf", "application/pdf"),
                title="  ",
            )
        self.assertEqual(title_error.exception.status_code, 422)

    def test_unsupported_and_oversized_uploads_are_rejected(self) -> None:
        unsupported_db = Mock()
        unsupported_db.scalar.return_value = project()
        with self.assertRaises(HTTPException) as unsupported_error:
            self._upload(
                unsupported_db,
                upload_file("notes.txt", b"text", "text/plain"),
            )
        self.assertEqual(unsupported_error.exception.status_code, 415)

        oversized_db = Mock()
        oversized_db.scalar.return_value = project()
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            documents.settings, "DOCUMENT_STORAGE_ROOT", Path(temp_directory)
        ), patch.object(documents.settings, "MAX_DOCUMENT_SIZE_MB", 0):
            with self.assertRaises(HTTPException) as oversized_error:
                self._upload(
                    oversized_db,
                    upload_file("requirements.pdf", b"too large", "application/pdf"),
                )
        self.assertEqual(oversized_error.exception.status_code, 413)

    def test_list_orders_by_newest_upload_and_scoped_lookup_isolated(self) -> None:
        newest = SimpleNamespace(id=DOCUMENT_ID, uploaded_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        oldest = SimpleNamespace(id=uuid.uuid4(), uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        list_db = Mock()
        list_db.scalar.return_value = project()
        list_db.scalars.return_value = [newest, oldest]

        response = documents.list_project_documents("RD", list_db)

        self.assertEqual(response, [newest, oldest])
        statement = list_db.scalars.call_args.args[0]
        self.assertIn("ORDER BY documents.uploaded_at DESC", str(statement))

        lookup_db = Mock()
        lookup_db.scalar.side_effect = [project(), None]
        with self.assertRaises(HTTPException) as lookup_error:
            documents.get_project_document("RD", DOCUMENT_ID, lookup_db)
        self.assertEqual(lookup_error.exception.status_code, 404)
        self.assertEqual(lookup_error.exception.detail, "Document not found")

    def test_database_failure_cleans_written_file(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        db.commit.side_effect = RuntimeError("synthetic database failure")
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            documents.settings, "DOCUMENT_STORAGE_ROOT", Path(temp_directory)
        ):
            with self.assertRaises(HTTPException) as error:
                self._upload(
                    db,
                    upload_file("requirements.pdf", b"pdf", "application/pdf"),
                )
            self.assertFalse((Path(temp_directory) / "RD").exists())

        self.assertEqual(error.exception.status_code, 500)
        self.assertEqual(db.rollback.call_count, 1)

    def test_post_commit_refresh_failure_preserves_stored_file(self) -> None:
        db = Mock()
        db.scalar.return_value = project()
        db.refresh.side_effect = RuntimeError("synthetic refresh failure")
        with tempfile.TemporaryDirectory() as temp_directory, patch.object(
            documents.settings, "DOCUMENT_STORAGE_ROOT", Path(temp_directory)
        ):
            with self.assertRaises(HTTPException) as error:
                self._upload(
                    db,
                    upload_file("requirements.pdf", b"pdf", "application/pdf"),
                )

            stored_files = list((Path(temp_directory) / "RD").rglob("requirements.pdf"))
            self.assertEqual(len(stored_files), 1)

        self.assertEqual(error.exception.status_code, 500)
        self.assertEqual(db.commit.call_count, 1)
        self.assertEqual(db.rollback.call_count, 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
