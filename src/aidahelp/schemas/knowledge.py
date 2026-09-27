"""知识检索接口模型。"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    strategy: Literal["vector", "bm25", "hybrid", "hybrid_rerank"] = "hybrid_rerank"
    top_k: int | None = Field(default=None, ge=1, le=50)
    category: str | None = Field(default=None, max_length=255)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query 不能只包含空白字符")
        return value


class EvidenceData(BaseModel):
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    section_path: str
    source_type: str
    category: str
    recall_score: float
    rerank_score: float | None
    retrieval_channel: str


class KnowledgeSearchData(BaseModel):
    query: str
    bm25_text: str
    strategy: str
    confidence: float
    confidence_signals: dict[str, float | int | bool]
    low_confidence: bool
    evidence: list[EvidenceData]
