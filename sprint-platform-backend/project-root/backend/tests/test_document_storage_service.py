from __future__ import annotations

import asyncio
import hashlib
import tempfile
import unittest
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.services.document_storage_service import (
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
    store_upload,
    validate_document_upload,
)


def upload_file(filename: str, content: bytes, mime_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": mime_type}),
    )


class FailingUpload:
    filename = "requirements.pdf"
    content_type = "application/pdf"

    def __init__(self) -> None:
        self._read_count = 0

    async def read(self, _size: int) -> bytes:
        self._read_count += 1
        if self._read_count == 1:
            return b"partial content"
        raise OSError("synthetic disk/read failure")


class DocumentStorageServiceTests(unittest.TestCase):
    def _store(
        self,
        storage_root: Path,
        upload: UploadFile,
        *,
        max_size_bytes: int = 1024,
    ):
        return asyncio.run(
            store_upload(
                upload,
                storage_root=storage_root,
                project_key="RD",
                document_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                max_size_bytes=max_size_bytes,
            )
        )

    def test_safe_pdf_is_stored_with_size_and_checksum(self) -> None:
        content = b"safe PDF content"
        with tempfile.TemporaryDirectory() as temp_directory:
            result = self._store(
                Path(temp_directory),
                upload_file("requirements.pdf", content, "application/pdf"),
            )

            self.assertEqual(result.original_filename, "requirements.pdf")
            self.assertEqual(result.mime_type, "application/pdf")
            self.assertEqual(result.file_size_bytes, len(content))
            self.assertEqual(result.checksum, hashlib.sha256(content).hexdigest())
            self.assertTrue((Path(temp_directory) / result.storage_path).is_file())

    def test_safe_docx_is_accepted(self) -> None:
        docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with tempfile.TemporaryDirectory() as temp_directory:
            result = self._store(
                Path(temp_directory), upload_file("design.docx", b"docx", docx_mime)
            )

            self.assertEqual(result.mime_type, docx_mime)
            self.assertEqual(result.file_size_bytes, 4)

    def test_unsupported_extension_and_mime_are_rejected(self) -> None:
        with self.assertRaises(UnsupportedDocumentTypeError):
            validate_document_upload("script.exe", "application/pdf")
        with self.assertRaises(UnsupportedDocumentTypeError):
            validate_document_upload("requirements.pdf", "text/plain")

    def test_path_traversal_filename_is_normalized_to_a_safe_basename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            result = self._store(
                Path(temp_directory),
                upload_file("../../private\\requirements.pdf", b"pdf", "application/pdf"),
            )

            self.assertEqual(result.original_filename, "requirements.pdf")
            self.assertEqual(
                result.storage_path,
                "RD/11111111-1111-1111-1111-111111111111/requirements.pdf",
            )

    def test_oversized_upload_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            with self.assertRaises(DocumentTooLargeError):
                self._store(
                    root,
                    upload_file("large.pdf", b"too large", "application/pdf"),
                    max_size_bytes=2,
                )

            self.assertFalse((root / "RD").exists())

    def test_partial_write_failure_removes_document_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            root = Path(temp_directory)
            with self.assertRaises(OSError):
                self._store(root, FailingUpload())

            self.assertFalse((root / "RD").exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
