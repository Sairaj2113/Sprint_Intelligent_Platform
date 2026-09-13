from __future__ import annotations

import unittest

from app.services.document_chunking_service import chunk_blocks
from app.services.document_extraction_service import ExtractedBlock


def block(
    text: str,
    *,
    page_number: int | None = None,
    section_title: str | None = None,
    source_type: str = "pdf",
) -> ExtractedBlock:
    metadata: dict[str, object] = {"source_type": source_type}
    if page_number is not None:
        metadata["page_number"] = page_number
    if section_title is not None:
        metadata["section_title"] = section_title
    return ExtractedBlock(text, page_number, section_title, metadata)


class DocumentChunkingServiceTests(unittest.TestCase):
    def test_short_block_creates_one_chunk_starting_at_zero(self) -> None:
        chunks = chunk_blocks([block("FastAPI supports RD-15.", page_number=1)], chunk_size_words=4, overlap_words=1)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].content, "FastAPI supports RD-15.")
        self.assertIsNone(chunks[0].token_count)
        self.assertEqual(chunks[0].page_number, 1)

    def test_long_block_uses_deterministic_word_overlap(self) -> None:
        chunks = chunk_blocks(
            [block("one two three four five six seven eight nine ten", page_number=2)],
            chunk_size_words=4,
            overlap_words=1,
        )

        self.assertEqual([chunk.chunk_index for chunk in chunks], [0, 1, 2])
        self.assertEqual(
            [chunk.content for chunk in chunks],
            ["one two three four", "four five six seven", "seven eight nine ten"],
        )
        self.assertTrue(all(chunk.page_number == 2 for chunk in chunks))

    def test_docx_paragraphs_in_one_section_form_one_chunk(self) -> None:
        chunks = chunk_blocks(
            [
                block("Architecture", section_title="Architecture", source_type="docx"),
                block("Paragraph A", section_title="Architecture", source_type="docx"),
                block("Paragraph B", section_title="Architecture", source_type="docx"),
                block("Paragraph C", section_title="Architecture", source_type="docx"),
            ],
            chunk_size_words=10,
            overlap_words=2,
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].content, "Paragraph A Paragraph B Paragraph C")
        self.assertEqual(chunks[0].section_title, "Architecture")
        self.assertEqual(chunks[0].metadata_json["source_type"], "docx")
        self.assertIsNone(chunks[0].page_number)
        self.assertIsNone(chunks[0].token_count)

    def test_docx_headings_remain_separate(self) -> None:
        chunks = chunk_blocks(
            [
                block("first section words", section_title="Architecture", source_type="docx"),
                block("second section words", section_title="Security", source_type="docx"),
            ],
            chunk_size_words=10,
            overlap_words=2,
        )

        self.assertEqual([chunk.section_title for chunk in chunks], ["Architecture", "Security"])
        self.assertEqual([chunk.metadata_json["source_type"] for chunk in chunks], ["docx", "docx"])

    def test_long_docx_section_splits_with_overlap(self) -> None:
        chunks = chunk_blocks(
            [
                block("one two three", section_title="Architecture", source_type="docx"),
                block("four five six seven eight", section_title="Architecture", source_type="docx"),
            ],
            chunk_size_words=4,
            overlap_words=1,
        )

        self.assertEqual([chunk.chunk_index for chunk in chunks], [0, 1, 2])
        self.assertEqual(
            [chunk.content for chunk in chunks],
            ["one two three four", "four five six seven", "seven eight"],
        )
        self.assertTrue(all(chunk.section_title == "Architecture" for chunk in chunks))

    def test_pdf_pages_remain_separate_even_when_short(self) -> None:
        chunks = chunk_blocks(
            [
                block("first page", page_number=1),
                block("second page", page_number=2),
            ],
            chunk_size_words=10,
            overlap_words=2,
        )

        self.assertEqual([chunk.content for chunk in chunks], ["first page", "second page"])
        self.assertEqual([chunk.page_number for chunk in chunks], [1, 2])

    def test_empty_input_and_invalid_overlap_are_handled(self) -> None:
        self.assertEqual(chunk_blocks([], chunk_size_words=4, overlap_words=1), [])
        with self.assertRaises(ValueError):
            chunk_blocks([block("words")], chunk_size_words=4, overlap_words=4)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
