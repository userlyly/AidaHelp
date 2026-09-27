"""知识文档和 Chunk 数据访问。"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import DocumentStatus, IndexStatus
from aidahelp.persistence.models.base import utc_now
from aidahelp.persistence.models.knowledge import (
    KnowledgeChunkModel,
    KnowledgeDocumentModel,
)


class KnowledgeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_document_by_version(
        self,
        *,
        checksum: str,
        version: str,
    ) -> KnowledgeDocumentModel | None:
        statement = select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.checksum == checksum,
            KnowledgeDocumentModel.version == version,
        )
        return await self.session.scalar(statement)

    async def get_document_by_id(self, document_id: str) -> KnowledgeDocumentModel | None:
        return await self.session.get(KnowledgeDocumentModel, document_id)

    async def list_chunks(
        self,
        *,
        document_id: str,
        pending_only: bool = False,
    ) -> list[KnowledgeChunkModel]:
        statement = (
            select(KnowledgeChunkModel)
            .where(KnowledgeChunkModel.document_id == document_id)
            .order_by(KnowledgeChunkModel.chunk_index.asc())
        )
        if pending_only:
            statement = statement.where(KnowledgeChunkModel.vector_status != IndexStatus.INDEXED)
        return list((await self.session.scalars(statement)).all())

    def add_document(
        self,
        *,
        title: str,
        source_type: str,
        content: str,
        checksum: str,
        version: str,
        source_uri: str | None = None,
        status: DocumentStatus = DocumentStatus.DRAFT,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocumentModel:
        document = KnowledgeDocumentModel(
            title=title,
            source_type=source_type,
            source_uri=source_uri,
            content=content,
            checksum=checksum,
            version=version,
            status=status,
            effective_from=effective_from,
            effective_to=effective_to,
            extra_data=metadata or {},
        )
        self.session.add(document)
        return document

    def add_chunk(
        self,
        *,
        document_id: str,
        chunk_index: int,
        content: str,
        section_path: str | None = None,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
        vector_id: str | None = None,
    ) -> KnowledgeChunkModel:
        chunk = KnowledgeChunkModel(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            section_path=section_path,
            token_count=token_count,
            extra_data=metadata or {},
            vector_id=vector_id,
            created_at=utc_now(),
        )
        self.session.add(chunk)
        return chunk

    def mark_document_indexed(self, document: KnowledgeDocumentModel, chunk_count: int) -> None:
        document.ingestion_status = IndexStatus.INDEXED
        document.chunk_count = chunk_count
        document.ingestion_error = None
        document.indexed_at = utc_now()

    def mark_document_failed(self, document: KnowledgeDocumentModel, error: str) -> None:
        document.ingestion_status = IndexStatus.FAILED
        document.ingestion_error = error[:2000]

    @staticmethod
    def mark_chunk_indexed(
        chunk: KnowledgeChunkModel,
        *,
        vector_id: str,
        embedding_model: str,
    ) -> None:
        chunk.vector_id = vector_id
        chunk.vector_status = IndexStatus.INDEXED
        chunk.embedding_model = embedding_model
