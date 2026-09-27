"""把内置工具和 MCP 工具合并成稳定、可查询的注册表。"""

import logging

from aidahelp.config import Settings
from aidahelp.tools.builtin import build_builtin_specs
from aidahelp.tools.mcp_client import fetch_mcp_specs
from aidahelp.tools.spec import ToolSpec

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._builtin = {item.name: item for item in build_builtin_specs()}

    async def all_specs(self, *, include_mcp: bool = True) -> list[ToolSpec]:
        merged = dict(self._builtin)
        # 单元测试不访问外部端口；staging/production 才验证真实 MCP 链路。
        if include_mcp and self.settings.environment != "testing":
            for spec in await fetch_mcp_specs(self.settings):
                if spec.name in merged:
                    logger.warning("MCP 工具重名，保留内置工具 name=%s", spec.name)
                    continue
                merged[spec.name] = spec
        # dict 保持插入顺序，稳定的工具前缀更有利于模型侧前缀缓存。
        return list(merged.values())

    async def by_name(self, name: str, *, include_mcp: bool = True) -> ToolSpec | None:
        return next(
            (item for item in await self.all_specs(include_mcp=include_mcp) if item.name == name),
            None,
        )
