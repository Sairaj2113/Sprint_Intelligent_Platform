"""Safe, streaming storage helpers for project-scoped document uploads."""

from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile


_MIME_TYPES_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
}
_STREAM_CHUNK_SIZE = 1024 * 1024


class DocumentStorageError(Exception):
    """A safe upload validation or storage error suitable for an HTTP response."""

    status_code = 500
    detail = "Unable to store document"


class InvalidDocumentFilenameError(DocumentStorageError):
    status_code = 422
    detail = "Document filename is required"


class UnsupportedDocumentTypeError(DocumentStorageError):
    status_code = 415
    detail = "Unsupported document type"


class DocumentTooLargeError(DocumentStorageError):
    status_code = 413
    detail = "Document exceeds maximum allowed size"


@dataclass(frozen=True)
class StoredDocument:
    """Metadata collected while a file is streamed to storage."""

    original_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    checksum: str


def safe_filename(filename: str | None) -> str:
    """Normalize a client filename to a basename without accepting path components."""
    if filename is None or not filename.strip():
        raise InvalidDocumentFilenameError()

    # Normalize Windows and POSIX separators before taking the final component.
    normalized = PurePosixPath(filename.replace("\\", "/")).name
    if normalized in {"", ".", ".."}:
        raise InvalidDocumentFilenameError()
    return normalized


def validate_document_upload(filename: str | None, content_type: str | None) -> tuple[str, str]:
    """Validate both extension and supplied MIME type before any file is written."""
    normalized_filename = safe_filename(filename)
    extension = Path(normalized_filename).suffix.lower()
    allowed_mime_types = _MIME_TYPES_BY_EXTENSION.get(extension)
    if allowed_mime_types is None:
        raise UnsupportedDocumentTypeError()

    normalized_mime_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_mime_type and normalized_mime_type not in allowed_mime_types:
        raise UnsupportedDocumentTypeError()

    # When a client does not supply MIME metadata, retain a canonical known type.
    return normalized_filename, normalized_mime_type or next(iter(allowed_mime_types))


def cleanup_stored_document(storage_root: Path, storage_path: str | Path) -> None:
    """Remove an upload directory only when it resolves inside the configured root."""
    root = storage_root.resolve()
    target = (root / storage_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return
    document_directory = target.parent
    project_directory = document_directory.parent
    shutil.rmtree(document_directory, ignore_errors=True)
    # Remove the project directory only when this failed upload was its last entry.
    if project_directory != root:
        try:
            project_directory.rmdir()
        except OSError:
            pass


async def store_upload(
    upload: UploadFile,
    *,
    storage_root: Path,
    project_key: str,
    document_id: uuid.UUID,
    max_size_bytes: int,
) -> StoredDocument:
    """Stream an allowed upload to a unique project/document directory and hash it."""
    filename, mime_type = validate_document_upload(upload.filename, upload.content_type)
    relative_path = Path(project_key) / str(document_id) / filename
    root = storage_root.resolve()
    destination = (root / relative_path).resolve()
    try:
        destination.relative_to(root)
    except ValueError as error:  # pragma: no cover - defensive path containment guard
        raise DocumentStorageError() from error

    try:
        destination.parent.mkdir(parents=True, exist_ok=False)
        digest = hashlib.sha256()
        file_size_bytes = 0
        with destination.open("xb") as stored_file:
            while content := await upload.read(_STREAM_CHUNK_SIZE):
                file_size_bytes += len(content)
                if file_size_bytes > max_size_bytes:
                    raise DocumentTooLargeError()
                digest.update(content)
                stored_file.write(content)
    except Exception:
        cleanup_stored_document(root, relative_path)
        raise

    return StoredDocument(
        original_filename=filename,
        storage_path=relative_path.as_posix(),
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        checksum=digest.hexdigest(),
    )
