"""HTTP 中间件。"""

import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from aidahelp.observability.logging import reset_trace_id, set_trace_id

logger = logging.getLogger(__name__)

# 只接受有限字符和长度的外部 trace_id，防止恶意请求把控制字符写进日志。
_SAFE_TRACE_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """为每个 HTTP 请求创建全链路标识，并记录请求耗时。"""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming_trace_id = request.headers.get("X-Trace-ID", "")
        trace_id = incoming_trace_id if _SAFE_TRACE_ID.fullmatch(incoming_trace_id) else uuid4().hex

        # request.state 供异常处理器读取；ContextVar 供深层业务日志自动读取。
        request.state.trace_id = trace_id
        context_token = set_trace_id(trace_id)
        started_at = perf_counter()

        logger.info(
            "收到 HTTP 请求",
            extra={
                "event": "request_started",
                "method": request.method,
                "path": request.url.path,
            },
        )

        try:
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.info(
                "HTTP 请求处理完成",
                extra={
                    "event": "request_finished",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )
            return response
        except Exception:
            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "HTTP 请求处理失败",
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            reset_trace_id(context_token)
