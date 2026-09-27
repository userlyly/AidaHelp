"""会话查询接口。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from aidahelp.api.dependencies import (
    get_conversation_service,
    get_current_principal,
    trusted_user_id,
)
from aidahelp.observability.logging import get_trace_id
from aidahelp.schemas.common import ApiResponse
from aidahelp.schemas.conversation import (
    ConversationData,
    CreateConversationRequest,
    MessageData,
)
from aidahelp.security.auth import UserPrincipal
from aidahelp.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["会话"])


@router.post(
    "",
    response_model=ApiResponse[ConversationData],
    status_code=status.HTTP_201_CREATED,
    summary="创建客服会话",
)
async def create_conversation(
    request: CreateConversationRequest,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
) -> ApiResponse[ConversationData]:
    user_id = trusted_user_id(principal, request.user_id)
    conversation = await service.create_conversation(
        user_id=user_id,
        title=request.title,
    )
    return ApiResponse(
        success=True,
        data=ConversationData.model_validate(conversation),
        trace_id=get_trace_id(),
    )


@router.get("", response_model=ApiResponse[list[ConversationData]], summary="查询我的会话列表")
async def list_conversations(
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
    user_id: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiResponse[list[ConversationData]]:
    owner_id = trusted_user_id(principal, user_id)
    conversations = await service.list_conversations(user_id=owner_id, limit=limit)
    return ApiResponse(
        success=True,
        data=[ConversationData.model_validate(item) for item in conversations],
        trace_id=get_trace_id(),
    )


@router.get(
    "/{conversation_id}",
    response_model=ApiResponse[ConversationData],
    summary="查询会话",
)
async def get_conversation(
    conversation_id: str,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
    user_id: Annotated[str | None, Query(max_length=36)] = None,
) -> ApiResponse[ConversationData]:
    owner_id = trusted_user_id(principal, user_id)
    conversation = await service.get_conversation(
        conversation_id=conversation_id,
        user_id=owner_id,
    )
    return ApiResponse(
        success=True,
        data=ConversationData.model_validate(conversation),
        trace_id=get_trace_id(),
    )


@router.get(
    "/{conversation_id}/messages",
    response_model=ApiResponse[list[MessageData]],
    summary="查询会话的原始消息",
)
async def list_messages(
    conversation_id: str,
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    principal: Annotated[UserPrincipal | None, Depends(get_current_principal)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user_id: Annotated[str | None, Query(max_length=36)] = None,
) -> ApiResponse[list[MessageData]]:
    owner_id = trusted_user_id(principal, user_id)
    messages = await service.list_messages(
        conversation_id=conversation_id,
        user_id=owner_id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        data=[MessageData.model_validate(message) for message in messages],
        trace_id=get_trace_id(),
    )
