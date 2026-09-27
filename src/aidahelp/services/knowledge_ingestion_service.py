"""知识文档解析、MySQL 落库与 Milvus 向量化。"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.config import Settings
from aidahelp.domain.enums import DocumentStatus, IndexStatus
from aidahelp.domain.exceptions import KnowledgeIngestionError
from aidahelp.integrations.embedding.base import EmbeddingModel
from aidahelp.knowledge.loaders import load_document
from aidahelp.knowledge.normalizer import normalize_text
from aidahelp.knowledge.splitter import split_document
from aidahelp.persistence.repositories.knowledge_repository import KnowledgeRepository
from aidahelp.persistence.vector_store.base import VectorRecord, VectorStore


@dataclass(frozen=True, slots=True)
class IngestionResult:
    document_id: str
    title: str
    chunk_count: int
    status: str
    reused: bool


@dataclass(frozen=True, slots=True)
class _ChunkSnapshot:
    id: str
    document_id: str
    chunk_index: int
    content: str
    section_path: str
    category: str


class KnowledgeIngestionService:
    """用状态机实现 MySQL 与 Milvus 的最终一致双写。"""

    def __init__(
        self,
        *,
        session: AsyncSession,
        embedding: EmbeddingModel,
        vector_store: VectorStore,
        settings: Settings,
    ) -> None:
        self.session = session
        self.embedding = embedding
        self.vector_store = vector_store
        self.settings = settings
        self.repository = KnowledgeRepository(session)

    async def ingest_file(
        self,
        path: str | Path,
        *,
        version: str,
        category: str | None = None,
        status: DocumentStatus = DocumentStatus.PUBLISHED,
    ) -> IngestionResult:
        loaded = load_document(path)
        content = normalize_text(loaded.content)
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        chunks = split_document(
            loaded,
            chunk_size=self.settings.knowledge_chunk_size,
            overlap=self.settings.knowledge_chunk_overlap,
            category=category,
        )
        if not chunks:
            raise KnowledgeIngestionError("文档切块结果为空")

        reused = False
        async with self.session.begin():
            document = await self.repository.get_document_by_version(
                checksum=checksum,
                version=version,
            )
            if document is None:
                document = self.repository.add_document(
                    title=loaded.title,
                    source_type=loaded.source_type,
                    source_uri=loaded.source_uri,
                    content=content,
                    checksum=checksum,
                    version=version,
                    status=status,
                    metadata={**loaded.metadata, "category": category or "general"},
                )
                await self.session.flush()
                for draft in chunks:
                    self.repository.add_chunk(
                        document_id=document.id,
                        chunk_index=draft.chunk_index,
                        content=draft.content,
                        section_path=draft.section_path,
                        token_count=draft.token_count,
                        metadata=draft.metadata,
                    )
                document.chunk_count = len(chunks)
                await self.session.flush()
            else:
                reused = True

        if document.ingestion_status != IndexStatus.INDEXED:
            await self._index_document(document.id, loaded.source_type)

        return IngestionResult(
            document_id=document.id,
            title=document.title,
            chunk_count=document.chunk_count,
            status=IndexStatus.INDEXED.value,
            reused=reused,
        )

    async def retry_document(self, document_id: str) -> IngestionResult:
        async with self.session.begin():
            document = await self.repository.get_document_by_id(document_id)
            if document is None:
                raise KnowledgeIngestionError("待重试的知识文档不存在")
            source_type = document.source_type
            title = document.title
        await self._index_document(document_id, source_type)
        return IngestionResult(
            document_id=document_id,
            title=title,
            chunk_count=document.chunk_count,
            status=IndexStatus.INDEXED.value,
            reused=True,
        )

    async def _index_document(self, document_id: str, source_type: str) -> None:
        try:
            async with self.session.begin():
                chunk_models = await self.repository.list_chunks(
                    document_id=document_id,
                    pending_only=True,
                )
                snapshots = [
                    _ChunkSnapshot(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        section_path=chunk.section_path or "",
                        category=str(chunk.extra_data.get("category") or "general"),
                    )
                    for chunk in chunk_models
                ]

            for start in range(0, len(snapshots), self.settings.embedding_batch_size):
                batch = snapshots[start : start + self.settings.embedding_batch_size]
                texts = [f"{item.section_path}\n{item.content}".strip() for item in batch]
                vectors = await self.embedding.embed_texts(texts)
                records = [
                    VectorRecord(
                        id=item.id,
                        document_id=item.document_id,
                        chunk_index=item.chunk_index,
                        dense=vector,
                        text=text,
                        content=item.content,
                        section_path=item.section_path,
                        source_type=source_type,
                        category=item.category,
                    )
                    for item, vector, text in zip(batch, vectors, texts, strict=True)
                ]
                await self.vector_store.upsert(records)
            if snapshots:
                await self.vector_store.flush()

            async with self.session.begin():
                document = await self.repository.get_document_by_id(document_id)
                if document is None:
                    raise KnowledgeIngestionError("向量化后找不到知识文档")
                stored_chunks = await self.repository.list_chunks(document_id=document_id)
                for chunk in stored_chunks:
                    self.repository.mark_chunk_indexed(
                        chunk,
                        vector_id=chunk.id,
                        embedding_model=self.embedding.name,
                    )
                self.repository.mark_document_indexed(document, len(stored_chunks))
        except Exception as exc:
            if self.session.in_transaction():
                await self.session.rollback()
            async with self.session.begin():
                document = await self.repository.get_document_by_id(document_id)
                if document is not None:
                    self.repository.mark_document_failed(document, str(exc))
            if isinstance(exc, KnowledgeIngestionError):
                raise
            raise KnowledgeIngestionError() from exc
