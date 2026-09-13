"""add document and pgvector foundation

Revision ID: c9e5f8a1b2d3
Revises: a3532753c1b1
Create Date: 2026-09-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c9e5f8a1b2d3"
down_revision: Union[str, None] = "a3532753c1b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


document_type = postgresql.ENUM(
    "PRD",
    "TRD",
    "ARCHITECTURE",
    "TESTING",
    "RELEASE",
    "DESIGN",
    "OTHER",
    name="document_type",
    create_type=False,
)
document_status = postgresql.ENUM(
    "UPLOADED",
    "PROCESSING",
    "PROCESSED",
    "FAILED",
    name="document_status",
    create_type=False,
)


def upgrade() -> None:
    """Create project-scoped document storage without modifying existing tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    document_type.create(bind, checkfirst=True)
    document_status.create(bind, checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            document_status,
            server_default=sa.text("'UPLOADED'"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_document_type", "documents", ["document_type"])
    op.create_index("ix_documents_status", "documents", ["status"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_title", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        # all-MiniLM-L6-v2 is expected to be the first 384-dimensional model.
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunks_document_chunk_index",
        ),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_project_id", "document_chunks", ["project_id"])


def downgrade() -> None:
    """Remove document tables and enums while retaining the shared vector extension."""
    op.drop_index("ix_document_chunks_project_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")

    bind = op.get_bind()
    document_status.drop(bind, checkfirst=True)
    document_type.drop(bind, checkfirst=True)
    # The extension is intentionally retained: it can be shared by other database objects.
