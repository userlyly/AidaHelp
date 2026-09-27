"""统一异常处理。

这里把框架异常转换为固定 JSON 结构。线上接口不直接返回 Python 堆栈，详细异常只写日志，
客户端可以拿 ``trace_id`` 请运维或开发人员查询对应日志。
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from aidahelp.domain.exceptions import DomainError
from aidahelp.observability.logging import get_trace_id
from aidahelp.schemas.common import ApiResponse, ErrorDetail

logger = logging.getLogger(__name__)


def _request_trace_id(request: Request) -> str:
    """中间件正常执行时从 request.state 读取，否则使用当前上下文的值。"""

    return getattr(request.state, "trace_id", get_trace_id())


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ApiResponse[None](
        success=False,
        error=ErrorDetail(code=code, message=message, details=details),
        trace_id=_request_trace_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload.model_dump()),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 注册项目统一的异常处理器。"""

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """把业务异常转换为稳定错误码，不让 Service 层依赖 HTTP 框架。"""

        logger.info(
            "业务规则拒绝请求",
            extra={"event": "domain_error", "error_code": exc.code},
        )
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "请求参数校验失败",
            extra={"event": "validation_failed", "path": request.url.path},
        )
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="请求参数不合法",
            details=exc.errors(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        # FastAPI 默认 404 返回结构与业务错误不同，这里也把它统一起来。
        message = exc.detail if isinstance(exc.detail, str) else "请求处理失败"
        details = None if isinstance(exc.detail, str) else exc.detail
        return _error_response(
            request,
            status_code=exc.status_code,
            code=f"HTTP_{exc.status_code}",
            message=message,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # exc_info 会把完整堆栈写入日志，但不会把内部实现泄露给客户端。
        logger.exception(
            "发生未处理异常",
            extra={"event": "unhandled_exception", "path": request.url.path},
        )
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="服务暂时不可用，请稍后重试",
        )
