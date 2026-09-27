"""知识检索 API。"""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends

from aidahelp.api.dependencies import get_current_principal, get_retrieval_service
from aidahelp.observability.logging import get_trace_id
from aidahelp.schemas.common import ApiResponse
from aidahelp.schemas.knowledge import EvidenceData, KnowledgeSearchData, KnowledgeSearchRequest
from aidahelp.security.auth import UserPrincipal
from aidahelp.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.post(
    "/search",
    response_model=ApiResponse[KnowledgeSearchData],
    summary="执行知识库混合检索",
)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    service: Annotated[RetrievalService, Depends(get_retrieval_service)],
    _principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
) -> ApiResponse[KnowledgeSearchData]:
    result = await service.search(
        request.query,
        strategy=request.strategy,
        top_k=request.top_k,
        category=request.category,
    )
    return ApiResponse(
        success=True,
        data=KnowledgeSearchData(
            query=result.rewritten.query,
            bm25_text=result.rewritten.bm25_text,
            strategy=result.strategy,
            confidence=result.confidence.score,
            confidence_signals=result.confidence.signals,
            low_confidence=result.low_confidence,
            evidence=[EvidenceData(**asdict(item)) for item in result.evidence],
        ),
        trace_id=get_trace_id(),
    )
