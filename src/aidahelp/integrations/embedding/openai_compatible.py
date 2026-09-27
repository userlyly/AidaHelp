"""OpenAI Embeddings 兼容接口适配器。"""

from typing import Any

import httpx

from aidahelp.integrations.embedding.errors import EmbeddingUpstreamError


class OpenAICompatibleEmbeddingModel:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @property
    def name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        try:
            response = await self._client.post(
                "embeddings",
                json={"model": self._model, "input": texts, "encoding_format": "float"},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            rows = sorted(payload["data"], key=lambda row: int(row["index"]))
            vectors = [list(map(float, row["embedding"])) for row in rows]
            if len(vectors) != len(texts) or any(
                len(vector) != self._dimension for vector in vectors
            ):
                raise ValueError("Embedding 返回数量或维度与配置不一致")
            return vectors
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise EmbeddingUpstreamError("Embedding 服务调用失败") from exc

    async def embed_query(self, query: str) -> list[float]:
        return (await self.embed_texts([query]))[0]

    async def close(self) -> None:
        await self._client.aclose()
