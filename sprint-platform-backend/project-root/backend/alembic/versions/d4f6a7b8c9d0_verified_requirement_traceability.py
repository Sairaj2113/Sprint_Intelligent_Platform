"""add verified requirement traceability

Revision ID: d4f6a7b8c9d0
Revises: c9e5f8a1b2d3
Create Date: 2026-09-29 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4f6a7b8c9d0"
down_revision: Union[str, None] = "c9e5f8a1b2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


requirement_trace_link_kind = postgresql.ENUM(
    "IMPLEMENTED_BY_ISSUE",
    "VERIFIED_BY_TEST",
    "RELEASED_BY_DEPLOYMENT",
    name="requirement_trace_link_kind",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    requirement_trace_link_kind.create(bind, checkfirst=True)

    op.create_table(
        "requirements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("requirement_key", sa.String(length=100), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_chunk_id", sa.UUID(), nullable=False),
        sa.Column("recorded_by_id", sa.UUID(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["document_chunks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "requirement_key", name="uq_requirements_project_key"),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_index("ix_requirements_source_chunk_id", "requirements", ["source_chunk_id"])

    op.create_table(
        "requirement_trace_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("requirement_id", sa.UUID(), nullable=False),
        sa.Column("link_kind", requirement_trace_link_kind, nullable=False),
        sa.Column("issue_id", sa.UUID(), nullable=True),
        sa.Column("test_result_id", sa.UUID(), nullable=True),
        sa.Column("deployment_id", sa.UUID(), nullable=True),
        sa.Column("verified_by_id", sa.UUID(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "((issue_id IS NOT NULL)::integer + (test_result_id IS NOT NULL)::integer + "
            "(deployment_id IS NOT NULL)::integer) = 1",
            name="ck_requirement_trace_links_exactly_one_target",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_result_id"], ["test_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_requirement_trace_links_project_id", "requirement_trace_links", ["project_id"])
    op.create_index("ix_requirement_trace_links_requirement_id", "requirement_trace_links", ["requirement_id"])
    op.create_index(
        "uq_requirement_trace_links_requirement_issue",
        "requirement_trace_links",
        ["requirement_id", "issue_id"],
        unique=True,
        postgresql_where=sa.text("issue_id IS NOT NULL"),
    )
    op.create_index(
        "uq_requirement_trace_links_requirement_test",
        "requirement_trace_links",
        ["requirement_id", "test_result_id"],
        unique=True,
        postgresql_where=sa.text("test_result_id IS NOT NULL"),
    )
    op.create_index(
        "uq_requirement_trace_links_requirement_deployment",
        "requirement_trace_links",
        ["requirement_id", "deployment_id"],
        unique=True,
        postgresql_where=sa.text("deployment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_requirement_trace_links_requirement_deployment", table_name="requirement_trace_links")
    op.drop_index("uq_requirement_trace_links_requirement_test", table_name="requirement_trace_links")
    op.drop_index("uq_requirement_trace_links_requirement_issue", table_name="requirement_trace_links")
    op.drop_index("ix_requirement_trace_links_requirement_id", table_name="requirement_trace_links")
    op.drop_index("ix_requirement_trace_links_project_id", table_name="requirement_trace_links")
    op.drop_table("requirement_trace_links")
    op.drop_index("ix_requirements_source_chunk_id", table_name="requirements")
    op.drop_index("ix_requirements_project_id", table_name="requirements")
    op.drop_table("requirements")
    requirement_trace_link_kind.drop(op.get_bind(), checkfirst=True)
