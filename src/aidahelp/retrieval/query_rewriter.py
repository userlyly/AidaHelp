"""不依赖 LLM 的基础结构化查询改写。"""

import re
from dataclasses import dataclass

_POLITE_PREFIX = re.compile(r"^(你好|您好|请问|麻烦问一下|我想问一下)[,，:：\s]*")
_SYNONYMS = {
    "邮费": ("运费", "配送费"),
    "运费": ("邮费", "配送费"),
    "寄过来": ("退货", "寄回"),
    "退钱": ("退款",),
    "坏了": ("故障", "质量问题", "保修"),
    "发货": ("出库", "配送"),
}


@dataclass(frozen=True, slots=True)
class RewrittenQuery:
    query: str
    bm25_text: str
    category: str | None = None


def rewrite_query(raw_query: str, category: str | None = None) -> RewrittenQuery:
    """Dense 使用干净问法；同义词扩展只给 BM25，避免污染语义向量。"""

    query = " ".join(_POLITE_PREFIX.sub("", raw_query.strip()).split())
    expansions: list[str] = []
    for term, synonyms in _SYNONYMS.items():
        if term in query:
            expansions.extend(synonym for synonym in synonyms if synonym not in query)
    bm25_text = " ".join(dict.fromkeys([query, *expansions]))
    return RewrittenQuery(query=query or raw_query.strip(), bm25_text=bm25_text, category=category)
