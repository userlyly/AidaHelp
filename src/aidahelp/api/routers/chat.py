"""Agent 聊天接口，同时提供普通 JSON 和前端使用的 SSE 传输。"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from aidahelp.api.dependencies import (
    get_agent_service,
    get_current_principal,
    trusted_user_id,
)
from aidahelp.observability.logging import get_trace_id
from aidahelp.schemas.chat import ChatRequest, ChatResponseData, ResumeRequest, TokenUsageData
from aidahelp.schemas.common import ApiResponse
from aidahelp.security.auth import UserPrincipal
from aidahelp.services.agent_service import AgentService

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post(
    "",
    response_model=ApiResponse[ChatResponseData],
    summary="执行一个完整 Agent 客服回合",
)
async def chat(
    request: ChatRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
) -> ApiResponse[ChatResponseData]:
    user_id = trusted_user_id(principal, request.user_id)
    result = await service.chat(
        user_id=user_id,
        conversation_id=request.conversation_id,
        message=request.message,
        title=request.title,
    )
    return ApiResponse(
        success=True,
        data=ChatResponseData(
            conversation_id=result.conversation_id,
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            answer=result.answer,
            model=result.model,
            usage=TokenUsageData(
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
            ),
            created_at=result.created_at,
            intent=result.intent,
            route=result.route,
            citations=result.citations,
            pending_action=result.pending_action,
        ),
        trace_id=get_trace_id(),
    )


@router.post(
    "/{conversation_id}/resume",
    response_model=ApiResponse[ChatResponseData],
    summary="确认或取消被 Agent 暂停的写操作",
)
async def resume_chat(
    conversation_id: str,
    request: ResumeRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
) -> ApiResponse[ChatResponseData]:
    user_id = trusted_user_id(principal, request.user_id)
    result = await service.resume(
        user_id=user_id,
        conversation_id=conversation_id,
        confirmed=request.confirmed,
    )
    return ApiResponse(
        success=True,
        data=ChatResponseData(
            conversation_id=result.conversation_id,
            user_message_id=result.user_message_id,
            assistant_message_id=result.assistant_message_id,
            answer=result.answer,
            model=result.model,
            usage=TokenUsageData(
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                total_tokens=result.usage.total_tokens,
            ),
            created_at=result.created_at,
            intent=result.intent,
            route=result.route,
            citations=result.citations,
            pending_action=result.pending_action,
        ),
        trace_id=get_trace_id(),
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


@router.post("/stream", summary="以 SSE 事件流执行 Agent 客服回合")
async def stream_chat(
    request: ChatRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
) -> StreamingResponse:
    user_id = trusted_user_id(principal, request.user_id)

    async def events():
        yield _sse({"event": "status", "message": "正在理解问题并选择处理流程…"})
        try:
            result = await service.chat(
                user_id=user_id,
                conversation_id=request.conversation_id,
                message=request.message,
                title=request.title,
            )
            yield _sse(
                {
                    "event": "meta",
                    "conversation_id": result.conversation_id,
                    "intent": result.intent,
                    "route": result.route,
                }
            )
            # 当前模型适配器完成一轮后分片发送；接口协议已为以后真正 token streaming 预留。
            for index in range(0, len(result.answer), 8):
                yield _sse({"event": "delta", "text": result.answer[index : index + 8]})
                await asyncio.sleep(0)
            if result.citations:
                yield _sse({"event": "citations", "items": result.citations})
            if result.pending_action:
                yield _sse({"event": "interrupt", "action": result.pending_action})
            yield _sse(
                {
                    "event": "done",
                    "conversation_id": result.conversation_id,
                    "assistant_message_id": result.assistant_message_id,
                }
            )
        except Exception as exc:
            yield _sse({"event": "error", "message": getattr(exc, "message", "客服暂时不可用")})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
