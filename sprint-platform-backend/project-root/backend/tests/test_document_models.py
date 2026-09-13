import unittest
import uuid

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models import Document, DocumentChunk, DocumentStatus, DocumentType, Project


class DocumentModelTests(unittest.TestCase):
    def test_document_can_be_instantiated(self) -> None:
        document = Document(
            project_id=uuid.uuid4(),
            document_type=DocumentType.PRD,
            title="Product requirements",
            original_filename="requirements.pdf",
            storage_path="documents/requirements.pdf",
        )

        self.assertEqual(document.document_type, DocumentType.PRD)
        self.assertEqual(
            Document.__table__.c.status.default.arg, DocumentStatus.UPLOADED
        )

    def test_document_chunk_can_be_instantiated(self) -> None:
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            chunk_index=0,
            content="Architecture overview",
            metadata_json={"source": "test"},
        )

        self.assertEqual(chunk.chunk_index, 0)
        self.assertEqual(chunk.metadata_json, {"source": "test"})

    def test_document_enum_values_are_stable(self) -> None:
        self.assertEqual(
            [item.value for item in DocumentType],
            ["PRD", "TRD", "ARCHITECTURE", "TESTING", "RELEASE", "DESIGN", "OTHER"],
        )
        self.assertEqual(
            [item.value for item in DocumentStatus],
            ["UPLOADED", "PROCESSING", "PROCESSED", "FAILED"],
        )

    def test_embedding_dimension_is_384(self) -> None:
        embedding_type = DocumentChunk.__table__.c.embedding.type
        self.assertEqual(embedding_type.dim, 384)

    def test_chunk_uniqueness_constraint_exists(self) -> None:
        constraints = [
            constraint
            for constraint in DocumentChunk.__table__.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        self.assertTrue(
            any(
                constraint.name == "uq_document_chunks_document_chunk_index"
                and [column.name for column in constraint.columns]
                == ["document_id", "chunk_index"]
                for constraint in constraints
            )
        )

    def test_required_foreign_keys_exist(self) -> None:
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in Document.__table__.foreign_keys},
            {"projects.id"},
        )
        self.assertEqual(
            {foreign_key.target_fullname for foreign_key in DocumentChunk.__table__.foreign_keys},
            {"documents.id", "projects.id"},
        )

    def test_relationships_configure(self) -> None:
        configure_mappers()
        self.assertEqual(Document.project.property.mapper.class_, Project)
        self.assertEqual(DocumentChunk.document.property.mapper.class_, Document)
        self.assertEqual(Project.documents.property.mapper.class_, Document)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
