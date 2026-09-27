"""结构化日志与请求 Trace 上下文。"""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

# ContextVar 与线程局部变量类似，但能正确支持 asyncio 并发任务。
# 两个请求即使同时执行，也不会拿到对方的 trace_id。
_trace_id_context: ContextVar[str] = ContextVar("trace_id", default="-")

# LogRecord 自带字段不属于业务信息，输出时需要排除。
_RESERVED_LOG_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


def get_trace_id() -> str:
    """获取当前异步请求的 trace_id。"""

    return _trace_id_context.get()


def set_trace_id(trace_id: str) -> Token[str]:
    """把 trace_id 写入当前请求上下文，并返回之后恢复上下文所需的 token。"""

    return _trace_id_context.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    """请求结束后恢复上下文，防止后台任务错误继承上一次请求的信息。"""

    _trace_id_context.reset(token)


class JsonFormatter(logging.Formatter):
    """把日志转换成一行 JSON，便于日志平台按字段搜索和统计。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", get_trace_id()),
        }

        # logging 的 extra 参数会进入 record.__dict__，这里把它们一并输出。
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_FIELDS and key not in payload:
                payload[key] = self._json_safe(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """尽量保留原类型；不能 JSON 序列化的对象退化为字符串。"""

        try:
            json.dumps(value)
        except (TypeError, ValueError):
            return str(value)
        return value


def configure_logging(level: str = "INFO") -> None:
    """初始化全局日志。

    每次创建测试应用时都可能调用该函数，因此先清空旧 handler，避免一条日志重复输出。
    """

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    # 让 Uvicorn 的日志也走统一 JSON 格式，方便以后接入 ELK 或 Loki。
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
