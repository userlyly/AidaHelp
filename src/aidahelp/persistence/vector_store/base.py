"""向量存储统一接口。"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class VectorRecord:
    id: str
    document_id: str
    chunk_index: int
    dense: list[float]
    text: str
    content: str
    section_path: str
    source_type: str
    category: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    id: str
    document_id: str
    chunk_index: int
    content: str
    section_path: str
    source_type: str
    category: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    async def upsert(self, records: list[VectorRecord]) -> None: ...

    async def flush(self) -> None: ...

    async def dense_search(
        self, vector: list[float], *, top_k: int, category: str | None = None
    ) -> list[SearchHit]: ...

    async def bm25_search(
        self, query: str, *, top_k: int, category: str | None = None
    ) -> list[SearchHit]: ...

    async def hybrid_search(
        self,
        vector: list[float],
        query: str,
        *,
        top_k: int,
        recall: int,
        category: str | None = None,
    ) -> list[SearchHit]: ...

    async def delete_document(self, document_id: str) -> None: ...

    async def ping(self) -> bool: ...

    async def close(self) -> None: ...
