"""阶段 5 的混合检索编排。"""

from dataclasses import dataclass
from typing import Literal

from aidahelp.config import Settings
from aidahelp.domain.exceptions import RetrievalUnavailableError
from aidahelp.integrations.embedding.base import EmbeddingModel
from aidahelp.integrations.reranker.base import Reranker
from aidahelp.persistence.vector_store.base import SearchHit, VectorStore
from aidahelp.retrieval.confidence import EvidenceConfidence, compute_confidence
from aidahelp.retrieval.query_rewriter import RewrittenQuery, rewrite_query

RetrievalStrategy = Literal["vector", "bm25", "hybrid", "hybrid_rerank"]


@dataclass(frozen=True, slots=True)
class RetrievedEvidence:
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


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    rewritten: RewrittenQuery
    strategy: RetrievalStrategy
    evidence: list[RetrievedEvidence]
    confidence: EvidenceConfidence
    low_confidence: bool


class RetrievalService:
    def __init__(
        self,
        *,
        embedding: EmbeddingModel,
        vector_store: VectorStore,
        reranker: Reranker,
        settings: Settings,
    ) -> None:
        self.embedding = embedding
        self.vector_store = vector_store
        self.reranker = reranker
        self.settings = settings

    async def search(
        self,
        raw_query: str,
        *,
        strategy: RetrievalStrategy = "hybrid_rerank",
        top_k: int | None = None,
        category: str | None = None,
    ) -> RetrievalResult:
        rewritten = rewrite_query(raw_query, category)
        final_top_k = top_k or self.settings.retrieval_top_k
        try:
            hits = await self._recall(rewritten, strategy, final_top_k)
            evidence = await self._rerank(rewritten.query, hits, strategy, final_top_k)
        except Exception as exc:
            raise RetrievalUnavailableError() from exc

        scores = [
            item.rerank_score if item.rerank_score is not None else item.recall_score
            for item in evidence
        ]
        confidence = compute_confidence(
            scores,
            [item.content for item in evidence],
            self.settings.rerank_min_score,
        )
        top_score = scores[0] if scores else 0.0
        low_confidence = confidence.score < self.settings.evidence_confidence_threshold or (
            strategy == "hybrid_rerank" and top_score < self.settings.rerank_min_score
        )
        return RetrievalResult(
            rewritten=rewritten,
            strategy=strategy,
            evidence=evidence,
            confidence=confidence,
            low_confidence=low_confidence,
        )

    async def _recall(
        self,
        query: RewrittenQuery,
        strategy: RetrievalStrategy,
        top_k: int,
    ) -> list[SearchHit]:
        if strategy == "bm25":
            return await self.vector_store.bm25_search(
                query.bm25_text,
                top_k=top_k,
                category=query.category,
            )

        vector = await self.embedding.embed_query(query.query)
        if strategy == "vector":
            return await self.vector_store.dense_search(
                vector,
                top_k=top_k,
                category=query.category,
            )

        recall = self.settings.retrieval_recall_top_k
        return await self.vector_store.hybrid_search(
            vector,
            query.bm25_text,
            top_k=recall if strategy == "hybrid_rerank" else top_k,
            recall=recall,
            category=query.category,
        )

    async def _rerank(
        self,
        query: str,
        hits: list[SearchHit],
        strategy: RetrievalStrategy,
        top_k: int,
    ) -> list[RetrievedEvidence]:
        if strategy != "hybrid_rerank" or not hits:
            return [self._to_evidence(hit, None) for hit in hits[:top_k]]

        documents = [f"{hit.section_path}\n{hit.content}".strip() for hit in hits]
        ranking = await self.reranker.rerank(query, documents, top_n=top_k)
        evidence = []
        for index, score in ranking:
            if 0 <= index < len(hits):
                evidence.append(self._to_evidence(hits[index], score))
        return evidence

    @staticmethod
    def _to_evidence(hit: SearchHit, rerank_score: float | None) -> RetrievedEvidence:
        return RetrievedEvidence(
            chunk_id=hit.id,
            document_id=hit.document_id,
            chunk_index=hit.chunk_index,
            content=hit.content,
            section_path=hit.section_path,
            source_type=hit.source_type,
            category=hit.category,
            recall_score=hit.score,
            rerank_score=rerank_score,
            retrieval_channel=str(hit.metadata.get("retrieval_channel") or "unknown"),
        )
