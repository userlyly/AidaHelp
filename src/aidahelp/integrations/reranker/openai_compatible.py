"""常见 ``/rerank`` HTTP 接口适配器。"""

from typing import Any

import httpx

from aidahelp.integrations.reranker.errors import RerankerUpstreamError


class OpenAICompatibleReranker:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    @property
    def name(self) -> str:
        return self._model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int,
    ) -> list[tuple[int, float]]:
        try:
            response = await self._client.post(
                "rerank",
                json={
                    "model": self._model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            results = payload.get("results") or payload.get("data")
            if not isinstance(results, list):
                raise ValueError("Reranker 响应缺少 results")
            ranked = [
                (int(item["index"]), float(item.get("relevance_score", item.get("score"))))
                for item in results
            ]
            return ranked[:top_n]
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise RerankerUpstreamError("Reranker 服务调用失败") from exc

    async def close(self) -> None:
        await self._client.aclose()
