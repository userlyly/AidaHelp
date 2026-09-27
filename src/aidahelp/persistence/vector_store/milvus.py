"""Milvus Standalone：Dense + 原生 BM25 + RRF 混合检索。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from aidahelp.persistence.vector_store.base import SearchHit, VectorRecord

_OUTPUT_FIELDS = [
    "document_id",
    "chunk_index",
    "content",
    "section_path",
    "source_type",
    "category",
]


class MilvusVectorStore:
    """把同步 pymilvus 固定在一个专用线程中，避免阻塞 FastAPI 事件循环。"""

    def __init__(
        self,
        *,
        uri: str,
        collection: str,
        dimension: int,
        token: str | None = None,
    ) -> None:
        self.uri = uri
        self.collection = collection
        self.dimension = dimension
        self.token = token
        self._client: MilvusClient | None = None
        self._collection_ready = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aidahelp-milvus")

    async def _call(self, function: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            partial(function, *args, **kwargs),
        )

    def _get_client(self) -> MilvusClient:
        if self._client is None:
            options: dict[str, Any] = {"uri": self.uri}
            if self.token:
                options["token"] = self.token
            self._client = MilvusClient(**options)
        return self._client

    def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        client = self._get_client()
        if client.has_collection(self.collection):
            client.load_collection(self.collection)
            self._collection_ready = True
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=36)
        schema.add_field("document_id", DataType.VARCHAR, max_length=36)
        schema.add_field("chunk_index", DataType.INT64)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=self.dimension)
        schema.add_field(
            "text",
            DataType.VARCHAR,
            max_length=16384,
            enable_analyzer=True,
            analyzer_params={"type": "chinese"},
        )
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("content", DataType.VARCHAR, max_length=8192)
        schema.add_field("section_path", DataType.VARCHAR, max_length=1024)
        schema.add_field("source_type", DataType.VARCHAR, max_length=32)
        schema.add_field("category", DataType.VARCHAR, max_length=255)
        schema.add_function(
            Function(
                name="text_bm25",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
        )

        indexes = client.prepare_index_params()
        indexes.add_index(field_name="dense", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index(
            field_name="sparse",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
        )
        client.create_collection(self.collection, schema=schema, index_params=indexes)
        client.load_collection(self.collection)
        self._collection_ready = True

    async def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return

        def work() -> None:
            self._ensure_collection()
            rows = [
                {
                    "id": record.id,
                    "document_id": record.document_id,
                    "chunk_index": record.chunk_index,
                    "dense": record.dense,
                    "text": record.text[:16384],
                    "content": record.content[:8192],
                    "section_path": record.section_path[:1024],
                    "source_type": record.source_type[:32],
                    "category": record.category[:255],
                }
                for record in records
            ]
            self._get_client().upsert(self.collection, rows)

        await self._call(work)

    async def flush(self) -> None:
        def work() -> None:
            self._ensure_collection()
            self._get_client().flush(self.collection)

        await self._call(work)

    async def dense_search(
        self,
        vector: list[float],
        *,
        top_k: int,
        category: str | None = None,
    ) -> list[SearchHit]:
        def work() -> list[SearchHit]:
            self._ensure_collection()
            result = self._get_client().search(
                self.collection,
                data=[vector],
                anns_field="dense",
                limit=top_k,
                output_fields=_OUTPUT_FIELDS,
                search_params={"metric_type": "COSINE"},
                filter=self._category_filter(category),
            )
            return [self._to_hit(hit, "dense") for hit in result[0]]

        return await self._call(work)

    async def bm25_search(
        self,
        query: str,
        *,
        top_k: int,
        category: str | None = None,
    ) -> list[SearchHit]:
        def work() -> list[SearchHit]:
            self._ensure_collection()
            result = self._get_client().search(
                self.collection,
                data=[query],
                anns_field="sparse",
                limit=top_k,
                output_fields=_OUTPUT_FIELDS,
                search_params={"metric_type": "BM25"},
                filter=self._category_filter(category),
            )
            return [self._to_hit(hit, "bm25") for hit in result[0]]

        return await self._call(work)

    async def hybrid_search(
        self,
        vector: list[float],
        query: str,
        *,
        top_k: int,
        recall: int,
        category: str | None = None,
    ) -> list[SearchHit]:
        def work() -> list[SearchHit]:
            self._ensure_collection()
            expression = self._category_filter(category)
            requests = [
                AnnSearchRequest(
                    data=[vector],
                    anns_field="dense",
                    param={"metric_type": "COSINE"},
                    limit=recall,
                    expr=expression,
                ),
                AnnSearchRequest(
                    data=[query],
                    anns_field="sparse",
                    param={"metric_type": "BM25"},
                    limit=recall,
                    expr=expression,
                ),
            ]
            result = self._get_client().hybrid_search(
                self.collection,
                reqs=requests,
                ranker=RRFRanker(),
                limit=top_k,
                output_fields=_OUTPUT_FIELDS,
            )
            return [self._to_hit(hit, "rrf") for hit in result[0]]

        return await self._call(work)

    async def delete_document(self, document_id: str) -> None:
        def work() -> None:
            self._ensure_collection()
            escaped = self._escape(document_id)
            self._get_client().delete(self.collection, filter=f'document_id == "{escaped}"')

        await self._call(work)

    async def ping(self) -> bool:
        try:
            return bool(await self._call(lambda: self._get_client().list_collections() is not None))
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._call(self._client.close)
        self._executor.shutdown(wait=False, cancel_futures=True)

    @classmethod
    def _category_filter(cls, category: str | None) -> str:
        return f'category == "{cls._escape(category)}"' if category else ""

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @staticmethod
    def _to_hit(hit: dict[str, Any], channel: str) -> SearchHit:
        entity = hit["entity"]
        return SearchHit(
            id=str(hit["id"]),
            document_id=str(entity["document_id"]),
            chunk_index=int(entity["chunk_index"]),
            content=str(entity["content"]),
            section_path=str(entity.get("section_path") or ""),
            source_type=str(entity.get("source_type") or ""),
            category=str(entity.get("category") or ""),
            score=float(hit["distance"]),
            metadata={"retrieval_channel": channel},
        )
