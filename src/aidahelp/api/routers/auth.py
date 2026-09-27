"""仅供非生产演示环境使用的登录入口。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.api.dependencies import get_db_session, get_request_settings, get_token_service
from aidahelp.config import Settings
from aidahelp.domain.enums import UserStatus
from aidahelp.domain.exceptions import AuthenticationError, AuthorizationError
from aidahelp.observability.logging import get_trace_id
from aidahelp.persistence.repositories.user_repository import UserRepository
from aidahelp.schemas.auth import DemoTokenRequest, TokenData
from aidahelp.schemas.common import ApiResponse
from aidahelp.security.auth import TokenService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/demo-token", response_model=ApiResponse[TokenData], summary="获取演示环境 Token")
async def issue_demo_token(
    request: DemoTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_request_settings)],
    tokens: Annotated[TokenService, Depends(get_token_service)],
) -> ApiResponse[TokenData]:
    if settings.is_production or not settings.demo_auth_enabled:
        raise AuthorizationError("演示登录在当前环境已关闭")
    async with session.begin():
        user = await UserRepository(session).get_by_external_id(request.external_user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise AuthenticationError("演示用户不存在或已停用，请先执行 seed 脚本")
    token, expires_at = tokens.issue(user_id=user.id)
    return ApiResponse(
        success=True,
        data=TokenData(
            access_token=token,
            expires_at=expires_at,
            user_id=user.id,
            nickname=user.nickname,
        ),
        trace_id=get_trace_id(),
    )
