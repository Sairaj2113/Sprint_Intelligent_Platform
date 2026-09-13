"""Deterministic, database-independent chunking for extracted document blocks."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.document_extraction_service import ExtractedBlock


@dataclass(frozen=True)
class ChunkData:
    chunk_index: int
    content: str
    token_count: int | None
    page_number: int | None
    section_title: str | None
    metadata_json: dict[str, object]


def _logical_blocks(blocks: list[ExtractedBlock]) -> list[ExtractedBlock]:
    """Group consecutive DOCX paragraphs by section while retaining PDF page boundaries."""
    logical_blocks: list[ExtractedBlock] = []
    position = 0
    while position < len(blocks):
        block = blocks[position]
        if block.metadata.get("source_type") != "docx":
            # PDF blocks stay independent, including when adjacent pages are short.
            logical_blocks.append(block)
            position += 1
            continue

        section_title = block.section_title
        grouped_blocks = [block]
        position += 1
        while (
            position < len(blocks)
            and blocks[position].metadata.get("source_type") == "docx"
            and blocks[position].section_title == section_title
        ):
            grouped_blocks.append(blocks[position])
            position += 1

        # Headings are already represented by section_title. Avoid repeating a heading
        # as chunk content when its section has actual body paragraphs.
        content_blocks = grouped_blocks
        if section_title:
            body_blocks = [item for item in grouped_blocks if item.text != section_title]
            if body_blocks:
                content_blocks = body_blocks

        logical_blocks.append(
            ExtractedBlock(
                text="\n\n".join(item.text for item in content_blocks),
                page_number=None,
                section_title=section_title,
                metadata=dict(block.metadata),
            )
        )
    return logical_blocks


def chunk_blocks(
    blocks: list[ExtractedBlock],
    *,
    chunk_size_words: int,
    overlap_words: int,
) -> list[ChunkData]:
    """Split PDF pages and grouped DOCX sections into deterministic word windows."""
    if chunk_size_words <= 0:
        raise ValueError("Document chunk size must be greater than zero")
    if overlap_words < 0 or overlap_words >= chunk_size_words:
        raise ValueError("Document chunk overlap must be smaller than chunk size")

    chunks: list[ChunkData] = []
    for block in _logical_blocks(blocks):
        words = block.text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(start + chunk_size_words, len(words))
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    content=" ".join(words[start:end]),
                    # Exact model tokenization is intentionally deferred to embedding work.
                    token_count=None,
                    page_number=block.page_number,
                    section_title=block.section_title,
                    metadata_json=dict(block.metadata),
                )
            )
            if end == len(words):
                break
            start = end - overlap_words
    return chunks
