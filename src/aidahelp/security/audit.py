"""安全事件审计；写入失败不影响主业务，但会留下错误日志。"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.observability.logging import get_trace_id
from aidahelp.persistence.models.agent_runtime import SecurityEventModel

logger = logging.getLogger(__name__)


async def record_security_event(
    session: AsyncSession,
    *,
    event_type: str,
    severity: str,
    reason: str,
    user_id: str | None = None,
    conversation_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    try:
        async with session.begin():
            session.add(
                SecurityEventModel(
                    event_type=event_type,
                    severity=severity,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    trace_id=get_trace_id(),
                    reason=reason[:512],
                    details=details or {},
                )
            )
    except Exception:
        await session.rollback()
        logger.exception("安全事件审计写入失败 event_type=%s", event_type)
