"""应用装配入口。

该模块使用“应用工厂”而不是在全局堆积初始化代码。好处是测试可以创建一份测试配置，
未来也能为不同部署环境装配不同的数据库或模型适配器。
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from aidahelp.api.error_handlers import register_exception_handlers
from aidahelp.api.middleware import TraceIdMiddleware
from aidahelp.api.routers.auth import router as auth_router
from aidahelp.api.routers.chat import router as chat_router
from aidahelp.api.routers.conversations import router as conversation_router
from aidahelp.api.routers.health import router as health_router
from aidahelp.api.routers.knowledge import router as knowledge_router
from aidahelp.config import Settings, get_settings
from aidahelp.integrations.embedding import build_embedding_model
from aidahelp.integrations.llm import build_chat_model
from aidahelp.integrations.reranker import build_reranker
from aidahelp.observability.logging import configure_logging
from aidahelp.persistence.database import Database
from aidahelp.persistence.vector_store import MilvusVectorStore
from aidahelp.security.auth import TokenService
from aidahelp.security.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from aidahelp.tools import ToolRegistry


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建并装配 FastAPI 应用。"""

    app_settings = settings or get_settings()
    if (
        app_settings.is_production
        and app_settings.auth_enabled
        and app_settings.auth_secret.get_secret_value() == "change-me-before-production-aidahelp"
    ):
        raise RuntimeError("生产环境必须配置独立的 AIDAHELP_AUTH_SECRET")
    configure_logging(app_settings.log_level)
    logger = logging.getLogger(__name__)
    database = Database(app_settings)
    chat_model = build_chat_model(app_settings)
    embedding_model = build_embedding_model(app_settings)
    reranker = build_reranker(app_settings)
    milvus_token = (
        app_settings.milvus_token.get_secret_value() if app_settings.milvus_token else None
    )
    vector_store = MilvusVectorStore(
        uri=app_settings.milvus_uri,
        token=milvus_token,
        collection=app_settings.milvus_collection,
        dimension=embedding_model.dimension,
    )
    tool_registry = ToolRegistry(app_settings)
    token_service = TokenService(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """管理整个应用生命周期，后续数据库连接池也在这里启动和关闭。"""

        checkpoint_context = None
        if app_settings.agent_enabled:
            checkpoint_path = Path(app_settings.checkpointer_db_path)
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_context = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
            app.state.checkpointer = await checkpoint_context.__aenter__()
            await app.state.checkpointer.setup()

        if app_settings.database_auto_create_schema:
            await database.create_schema_for_tests()

        database_ready = await database.ping()
        logger.info(
            "AidaHelp 服务启动",
            extra={
                "event": "application_started",
                "environment": app_settings.environment,
                "version": app_settings.version,
                "database_url": database.safe_url,
                "database_ready": database_ready,
            },
        )
        try:
            yield
        finally:
            if checkpoint_context is not None:
                await checkpoint_context.__aexit__(None, None, None)
            await chat_model.close()
            await reranker.close()
            await embedding_model.close()
            await vector_store.close()
            await database.dispose()
            logger.info("AidaHelp 服务停止", extra={"event": "application_stopped"})

    docs_url = "/docs" if app_settings.docs_enabled else None
    openapi_url = "/openapi.json" if app_settings.docs_enabled else None
    app = FastAPI(
        title=app_settings.service_name,
        version=app_settings.version,
        debug=app_settings.debug,
        docs_url=docs_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # 通过 app.state 保存“应用级对象”，而不是使用难以替换的全局变量。
    app.state.settings = app_settings
    app.state.database = database
    app.state.chat_model = chat_model
    app.state.embedding_model = embedding_model
    app.state.reranker = reranker
    app.state.vector_store = vector_store
    app.state.tool_registry = tool_registry
    app.state.token_service = token_service
    app.state.checkpointer = None

    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, settings=app_settings)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=app_settings.max_request_body_bytes,
    )
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=app_settings.rate_limit_requests_per_minute,
    )
    allowed_origins = [
        item.strip() for item in app_settings.cors_allowed_origins.split(",") if item.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Trace-ID"],
        )
    register_exception_handlers(app)
    app.include_router(auth_router, prefix=app_settings.api_prefix)
    app.include_router(health_router, prefix=app_settings.api_prefix)
    app.include_router(conversation_router, prefix=app_settings.api_prefix)
    app.include_router(chat_router, prefix=app_settings.api_prefix)
    app.include_router(knowledge_router, prefix=app_settings.api_prefix)

    web_dir = Path(__file__).resolve().parents[2] / "web"
    app.mount("/assets", StaticFiles(directory=web_dir), name="assets")

    @app.get("/", include_in_schema=False, response_model=None)
    async def root() -> Response:
        """部署后直接打开可交互客服页面。"""

        return FileResponse(web_dir / "index.html")

    return app
