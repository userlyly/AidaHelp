"""精排模型协议。"""

from typing import Protocol


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int,
    ) -> list[tuple[int, float]]: ...

    async def close(self) -> None: ...
