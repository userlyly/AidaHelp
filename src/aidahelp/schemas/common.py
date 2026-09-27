"""各接口共用的响应结构。"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """机器可识别的错误码，以及给人阅读的错误说明。"""

    code: str
    message: str
    details: Any | None = None


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 外壳，前端不必为每个接口猜测成功和失败的数据结构。"""

    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    trace_id: str


class HealthData(BaseModel):
    """健康检查返回的数据。"""

    service: str
    version: str
    environment: str
    status: str = "ok"
    timestamp: datetime
    checks: dict[str, str] = Field(default_factory=dict)
