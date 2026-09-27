"""知识文档与知识 Chunk ORM 模型。"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from aidahelp.domain.enums import DocumentStatus, IndexStatus, enum_values
from aidahelp.persistence.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class KnowledgeDocumentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """一份知识文档及其版本信息。"""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("uq_knowledge_documents_checksum_version", "checksum", "version", unique=True),
        Index("ix_knowledge_documents_status_effective", "status", "effective_from"),
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # MySQL 的普通 TEXT 最多约 64KB；LONGTEXT 可以容纳较大的原始文档。
    content: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=DocumentStatus.DRAFT,
        server_default=DocumentStatus.DRAFT.value,
        nullable=False,
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    ingestion_status: Mapped[IndexStatus] = mapped_column(
        Enum(
            IndexStatus,
            name="document_index_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=IndexStatus.PENDING,
        server_default=IndexStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KnowledgeChunkModel(UUIDPrimaryKeyMixin, Base):
    """从知识文档中切出来的检索单元。阶段 3 会正式生成并写入这些数据。"""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("uq_knowledge_chunks_document_index", "document_id", "chunk_index", unique=True),
        Index("ix_knowledge_chunks_document", "document_id"),
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=False)
    section_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    # vector_id 是 MySQL 文本记录与 Milvus 向量记录之间的关联键。
    vector_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    vector_status: Mapped[IndexStatus] = mapped_column(
        Enum(
            IndexStatus,
            name="chunk_index_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=32,
        ),
        default=IndexStatus.PENDING,
        server_default=IndexStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
