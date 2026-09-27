"""服务健康检查接口。"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from aidahelp.api.dependencies import get_database, get_request_settings
from aidahelp.config import Settings
from aidahelp.observability.logging import get_trace_id
from aidahelp.persistence.database import Database
from aidahelp.schemas.common import ApiResponse, ErrorDetail, HealthData

router = APIRouter(prefix="/health", tags=["系统状态"])


def _health_data(settings: Settings, checks: dict[str, str]) -> HealthData:
    return HealthData(
        service=settings.service_name,
        version=settings.version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
        checks=checks,
    )


@router.get(
    "/live",
    response_model=ApiResponse[HealthData],
    summary="存活检查",
)
async def liveness(
    settings: Annotated[Settings, Depends(get_request_settings)],
) -> ApiResponse[HealthData]:
    """只回答“Web 进程是否还活着”，适合容器平台判断是否需要重启进程。"""

    return ApiResponse(
        success=True,
        data=_health_data(settings, {"application": "ok"}),
        trace_id=get_trace_id(),
    )


@router.get(
    "/ready",
    response_model=ApiResponse[HealthData],
    summary="就绪检查",
)
async def readiness(
    settings: Annotated[Settings, Depends(get_request_settings)],
    database: Annotated[Database, Depends(get_database)],
    response: Response,
) -> ApiResponse[HealthData]:
    """回答“服务能否接客”。

    MySQL 不可用时，进程仍然“存活”，但已经无法保存会话，因此就绪检查返回 503。
    """

    mysql_ok = await database.ping()
    checks = {"application": "ok", "mysql": "ok" if mysql_ok else "error"}
    if not mysql_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ApiResponse(
            success=False,
            data=HealthData(
                **_health_data(settings, checks).model_dump(exclude={"status"}),
                status="not_ready",
            ),
            error=ErrorDetail(
                code="DATABASE_NOT_READY",
                message="MySQL 暂时不可用",
            ),
            trace_id=get_trace_id(),
        )

    return ApiResponse(
        success=True,
        data=_health_data(settings, checks),
        trace_id=get_trace_id(),
    )
