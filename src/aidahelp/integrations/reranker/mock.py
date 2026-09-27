"""用于离线跑通流程的词项重叠精排器。"""

import re

_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+")


class LexicalReranker:
    @property
    def name(self) -> str:
        return "mock-lexical-reranker"

    async def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        top_n: int,
    ) -> list[tuple[int, float]]:
        query_terms = set(_TOKEN.findall(query.lower()))
        ranked = []
        for index, document in enumerate(documents):
            document_terms = set(_TOKEN.findall(document.lower()))
            if not query_terms:
                score = 0.0
            else:
                score = len(query_terms & document_terms) / len(query_terms)
            ranked.append((index, round(float(score), 6)))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_n]

    async def close(self) -> None:
        pass
