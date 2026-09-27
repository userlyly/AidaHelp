"""无模型依赖的确定性 Hash Embedding。"""

import hashlib
import math
import re

_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


class HashEmbeddingModel:
    """用于跑通入库链路，不代表真实语义模型效果。"""

    def __init__(self, dimension: int) -> None:
        self._dimension = dimension

    @property
    def name(self) -> str:
        return f"mock-hash-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in _TOKEN.findall(text.lower()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    async def close(self) -> None:
        pass
