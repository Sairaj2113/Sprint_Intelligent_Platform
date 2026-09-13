"""Pure file-system document text extraction for uploaded project documents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class DocumentExtractionError(Exception):
    """Controlled extraction failure that is safe to expose to an API client."""

    status_code = 422
    detail = "Unable to extract text from document"


class NoExtractableTextError(DocumentExtractionError):
    detail = "No extractable text found in document"


@dataclass(frozen=True)
class ExtractedBlock:
    text: str
    page_number: int | None
    section_title: str | None
    metadata: dict[str, object]


def normalize_text(text: str) -> str:
    """Normalize line endings, edge whitespace, and repeated blank lines only."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.strip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def resolve_document_path(storage_root: Path, storage_path: str) -> Path:
    """Resolve an internal path and reject any path outside the configured storage root."""
    root = storage_root.resolve()
    path = (root / storage_path).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise DocumentExtractionError("Invalid document storage path") from error
    if not path.is_file():
        raise DocumentExtractionError("Stored document file is unavailable")
    return path


def extract_pdf(path: Path) -> list[ExtractedBlock]:
    """Extract non-empty PDF page text in original page order without OCR."""
    try:
        reader = PdfReader(path)
        blocks = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                blocks.append(
                    ExtractedBlock(
                        text=text,
                        page_number=page_number,
                        section_title=None,
                        metadata={"source_type": "pdf", "page_number": page_number},
                    )
                )
    except NoExtractableTextError:
        raise
    except Exception as error:
        raise DocumentExtractionError() from error
    if not blocks:
        raise NoExtractableTextError()
    return blocks


def _is_heading_style(style_name: str | None) -> bool:
    return bool(style_name and style_name.lower().startswith("heading"))


def extract_docx(path: Path) -> list[ExtractedBlock]:
    """Extract DOCX paragraphs in order while carrying forward the active heading."""
    try:
        document = DocxDocument(path)
        blocks = []
        section_title: str | None = None
        for paragraph in document.paragraphs:
            text = normalize_text(paragraph.text)
            if not text:
                continue
            if _is_heading_style(getattr(paragraph.style, "name", None)):
                section_title = text
            metadata: dict[str, object] = {"source_type": "docx"}
            if section_title:
                metadata["section_title"] = section_title
            blocks.append(
                ExtractedBlock(
                    text=text,
                    page_number=None,
                    section_title=section_title,
                    metadata=metadata,
                )
            )
    except Exception as error:
        raise DocumentExtractionError() from error
    if not blocks:
        raise NoExtractableTextError()
    return blocks


def extract_document(
    *,
    storage_root: Path,
    storage_path: str,
    original_filename: str,
) -> list[ExtractedBlock]:
    """Resolve and extract one supported stored file without accessing the database."""
    path = resolve_document_path(storage_root, storage_path)
    suffix = Path(original_filename).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix == ".docx":
        return extract_docx(path)
    raise DocumentExtractionError("Unsupported stored document type")
