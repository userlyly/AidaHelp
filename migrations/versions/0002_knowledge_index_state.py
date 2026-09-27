"""Add resumable knowledge indexing state.

Revision ID: 0002_knowledge_index_state
Revises: 0001_initial_schema
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_knowledge_index_state"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    status_type = sa.Enum(
        "pending", "indexed", "failed", native_enum=False, create_constraint=False, length=32
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("ingestion_status", status_type, server_default="pending", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("knowledge_documents", sa.Column("ingestion_error", sa.Text(), nullable=True))
    op.add_column(
        "knowledge_documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_knowledge_documents_document_index_status",
        "knowledge_documents",
        "ingestion_status IN ('pending', 'indexed', 'failed')",
    )
    op.create_index(
        "ix_knowledge_documents_ingestion_status",
        "knowledge_documents",
        ["ingestion_status"],
    )

    op.add_column(
        "knowledge_chunks",
        sa.Column("vector_status", status_type, server_default="pending", nullable=False),
    )
    op.add_column("knowledge_chunks", sa.Column("embedding_model", sa.String(128), nullable=True))
    op.create_check_constraint(
        "ck_knowledge_chunks_chunk_index_status",
        "knowledge_chunks",
        "vector_status IN ('pending', 'indexed', 'failed')",
    )
    op.create_index("ix_knowledge_chunks_vector_status", "knowledge_chunks", ["vector_status"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_vector_status", table_name="knowledge_chunks")
    op.drop_constraint("ck_knowledge_chunks_chunk_index_status", "knowledge_chunks", type_="check")
    op.drop_column("knowledge_chunks", "embedding_model")
    op.drop_column("knowledge_chunks", "vector_status")

    op.drop_index("ix_knowledge_documents_ingestion_status", table_name="knowledge_documents")
    op.drop_constraint(
        "ck_knowledge_documents_document_index_status",
        "knowledge_documents",
        type_="check",
    )
    op.drop_column("knowledge_documents", "indexed_at")
    op.drop_column("knowledge_documents", "ingestion_error")
    op.drop_column("knowledge_documents", "chunk_count")
    op.drop_column("knowledge_documents", "ingestion_status")
