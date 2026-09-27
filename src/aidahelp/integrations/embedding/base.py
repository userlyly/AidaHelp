"""与具体厂商无关的 Embedding 协议。"""

from typing import Protocol


class EmbeddingModel(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, query: str) -> list[float]: ...

    async def close(self) -> None: ...
