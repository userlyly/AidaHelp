"""工具执行唯一入口：校验 → 权限 → 超时/重试 → 截断 → 审计。"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.config import Settings
from aidahelp.domain.enums import ToolPermission, ToolRunStatus
from aidahelp.persistence.models.agent_runtime import ToolAuditModel
from aidahelp.security.guardrails import SecurityGuard
from aidahelp.tools.spec import ToolContext, ToolSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ToolRunResult:
    tool_call_id: str
    name: str
    ok: bool
    status: ToolRunStatus
    content: str
    retry_count: int
    duration_ms: int


class ToolExecutor:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.security = SecurityGuard(settings.guardrails_enabled)

    async def execute(
        self,
        *,
        spec: ToolSpec | None,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        user_id: str,
        conversation_id: str,
        confirmed: bool = False,
    ) -> ToolRunResult:
        started = time.monotonic()
        if spec is None:
            return await self._finish(
                None,
                tool_call_id,
                name,
                arguments,
                False,
                ToolRunStatus.FAILED,
                f"未知工具：{name}",
                0,
                started,
                conversation_id,
            )
        try:
            errors = list(Draft202012Validator(spec.json_schema).iter_errors(arguments))
        except Exception as exc:
            return await self._finish(
                spec,
                tool_call_id,
                name,
                arguments,
                False,
                ToolRunStatus.FAILED,
                f"工具参数定义异常：{type(exc).__name__}",
                0,
                started,
                conversation_id,
            )
        if errors:
            return await self._finish(
                spec,
                tool_call_id,
                name,
                arguments,
                False,
                ToolRunStatus.VALIDATION_REJECTED,
                f"参数校验失败：{errors[0].message}",
                0,
                started,
                conversation_id,
            )
        if spec.permission == ToolPermission.WRITE and not confirmed:
            return await self._finish(
                spec,
                tool_call_id,
                name,
                arguments,
                False,
                ToolRunStatus.PERMISSION_REJECTED,
                "写操作尚未获得用户确认，已拒绝执行。",
                0,
                started,
                conversation_id,
            )

        timeout = spec.timeout_seconds or (
            self.settings.mcp_tool_timeout
            if spec.source == "mcp"
            else self.settings.tool_default_timeout
        )
        retries = (
            0
            if spec.permission == ToolPermission.WRITE
            else (self.settings.tool_max_retries if spec.max_retries is None else spec.max_retries)
        )
        context = ToolContext(self.session, user_id, conversation_id)
        for attempt in range(retries + 1):
            try:
                value = await asyncio.wait_for(spec.handler(arguments, context), timeout=timeout)
                content = self._serialize(value)
                return await self._finish(
                    spec,
                    tool_call_id,
                    name,
                    arguments,
                    True,
                    ToolRunStatus.SUCCEEDED,
                    content,
                    attempt,
                    started,
                    conversation_id,
                )
            except TimeoutError:
                if attempt < retries:
                    continue
                return await self._finish(
                    spec,
                    tool_call_id,
                    name,
                    arguments,
                    False,
                    ToolRunStatus.TIMED_OUT,
                    "工具执行超时，请稍后重试。",
                    attempt,
                    started,
                    conversation_id,
                )
            except Exception as exc:
                return await self._finish(
                    spec,
                    tool_call_id,
                    name,
                    arguments,
                    False,
                    ToolRunStatus.FAILED,
                    f"工具执行失败：{type(exc).__name__}",
                    attempt,
                    started,
                    conversation_id,
                )
        raise AssertionError("unreachable")

    def _serialize(self, value: Any) -> str:
        content = (
            value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        )
        limit = self.settings.tool_result_max_chars
        content = content if len(content) <= limit else content[:limit] + "…(结果已截断)"
        return self.security.sanitize_untrusted(content, max_chars=limit, wrap=False)

    async def _finish(
        self,
        spec: ToolSpec | None,
        tool_call_id: str,
        name: str,
        arguments: dict[str, Any],
        ok: bool,
        status: ToolRunStatus,
        content: str,
        retry_count: int,
        started: float,
        conversation_id: str,
    ) -> ToolRunResult:
        duration_ms = int((time.monotonic() - started) * 1000)
        try:
            async with self.session.begin():
                self.session.add(
                    ToolAuditModel(
                        conversation_id=conversation_id,
                        tool_call_id=tool_call_id or None,
                        tool_name=name or "unknown",
                        source=spec.source if spec else "unknown",
                        mcp_server=spec.mcp_server if spec else None,
                        permission=spec.permission if spec else ToolPermission.READ,
                        arguments=arguments,
                        result_summary=content[:500] if ok else None,
                        status=status,
                        error_message=None if ok else content[:512],
                        retry_count=retry_count,
                        duration_ms=duration_ms,
                    )
                )
        except Exception:
            # 审计是旁路能力：落库失败要记录日志，但不能把成功的业务查询改判成失败。
            logger.exception("工具审计写入失败 tool=%s status=%s", name, status.value)
            await self.session.rollback()
        return ToolRunResult(
            tool_call_id=tool_call_id,
            name=name,
            ok=ok,
            status=status,
            content=content,
            retry_count=retry_count,
            duration_ms=duration_ms,
        )
