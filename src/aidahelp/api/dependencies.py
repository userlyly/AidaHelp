"""FastAPI 依赖项。

依赖函数负责把应用级 Database 转换成请求级 Session，路由无需了解连接池细节。
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.config import Settings
from aidahelp.domain.enums import UserStatus
from aidahelp.domain.exceptions import AuthenticationError, AuthorizationError
from aidahelp.integrations.embedding.base import EmbeddingModel
from aidahelp.integrations.llm.base import ChatModel
from aidahelp.integrations.reranker.base import Reranker
from aidahelp.persistence.database import Database
from aidahelp.persistence.repositories.user_repository import UserRepository
from aidahelp.persistence.vector_store.base import VectorStore
from aidahelp.security.audit import record_security_event
from aidahelp.security.auth import TokenService, UserPrincipal
from aidahelp.services.agent_service import AgentService
from aidahelp.services.chat_service import ChatService
from aidahelp.services.conversation_service import ConversationService
from aidahelp.services.retrieval_service import RetrievalService

_bearer = HTTPBearer(auto_error=False)


def get_request_settings(request: Request) -> Settings:
    """从应用状态读取配置，测试时可以注入一份独立配置。"""

    return request.app.state.settings


def get_database(request: Request) -> Database:
    """获取应用启动时创建的数据库连接池管理器。"""

    return request.app.state.database


def get_chat_model(request: Request) -> ChatModel:
    """获取应用级模型客户端，复用其 HTTP 连接池。"""

    return request.app.state.chat_model


def get_embedding_model(request: Request) -> EmbeddingModel:
    return request.app.state.embedding_model


def get_vector_store(request: Request) -> VectorStore:
    return request.app.state.vector_store


def get_reranker(request: Request) -> Reranker:
    return request.app.state.reranker


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


async def get_db_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    """每个请求独享一个 Session，请求结束后自动关闭。"""

    async with database.session() as session:
        yield session


async def get_current_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserPrincipal | None:
    """从 Bearer Token 获取可信 user_id；测试环境保留无 Token 的兼容入口。"""

    settings: Settings = request.app.state.settings
    if not settings.auth_enabled:
        return None
    if credentials is None:
        if settings.environment == "testing":
            return None
        await record_security_event(
            session,
            event_type="authentication_missing",
            severity="medium",
            reason="受保护接口未携带 Bearer Token",
        )
        raise AuthenticationError()
    try:
        principal = request.app.state.token_service.verify(credentials.credentials)
    except AuthenticationError:
        await record_security_event(
            session,
            event_type="authentication_failed",
            severity="high",
            reason="Bearer Token 验证失败",
        )
        raise
    async with session.begin():
        user = await UserRepository(session).get_by_id(principal.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            invalid_user = True
        else:
            invalid_user = False
    if invalid_user:
        await record_security_event(
            session,
            event_type="disabled_user_access",
            severity="high",
            user_id=principal.user_id,
            reason="用户不存在或已被停用",
        )
        raise AuthenticationError("用户不存在或已被停用")
    return principal


def trusted_user_id(principal: UserPrincipal | None, requested_user_id: str | None) -> str:
    """Token 身份优先，客户端不能通过修改 user_id 冒充其他用户。"""

    if principal is not None:
        if requested_user_id and requested_user_id != principal.user_id:
            raise AuthorizationError("请求中的 user_id 与登录身份不一致")
        return principal.user_id
    if requested_user_id:
        return requested_user_id
    raise AuthenticationError()


def get_conversation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationService:
    return ConversationService(session)


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    model: Annotated[ChatModel, Depends(get_chat_model)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> ChatService:
    return ChatService(session=session, model=model, settings=settings)


def get_retrieval_service(
    embedding: Annotated[EmbeddingModel, Depends(get_embedding_model)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    reranker: Annotated[Reranker, Depends(get_reranker)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> RetrievalService:
    return RetrievalService(
        embedding=embedding,
        vector_store=vector_store,
        reranker=reranker,
        settings=settings,
    )


def get_agent_service(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    model: Annotated[ChatModel, Depends(get_chat_model)],
    retrieval: Annotated[RetrievalService, Depends(get_retrieval_service)],
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> AgentService:
    return AgentService(
        session=session,
        model=model,
        retrieval=retrieval,
        registry=request.app.state.tool_registry,
        checkpointer=request.app.state.checkpointer,
        settings=settings,
    )
