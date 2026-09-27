"""MCP 动态发现与调用。

每轮现拉工具清单，外部 Server 新增只读工具后无需修改 Agent 核心代码。
"""

import logging
from typing import Any

from aidahelp.config import Settings
from aidahelp.tools.spec import ToolContext, ToolSpec

logger = logging.getLogger(__name__)


async def _call_mcp_tool(url: str, name: str, arguments: dict[str, Any]) -> Any:
    # 延迟导入：未安装可选依赖时，基础代码仍可被静态分析。
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments=arguments)
            return [
                block.model_dump(mode="json") if hasattr(block, "model_dump") else str(block)
                for block in result.content
            ]


async def fetch_mcp_specs(settings: Settings) -> list[ToolSpec]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    specs: list[ToolSpec] = []
    connections = {
        "logistics": settings.mcp_logistics_url,
        "aftersales": settings.mcp_aftersales_url,
    }
    for server_name, url in connections.items():
        try:
            async with streamable_http_client(url) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.list_tools()
            for tool in result.tools:
                tool_name = tool.name

                async def handler(
                    arguments: dict[str, Any],
                    context: ToolContext,
                    *,
                    _url: str = url,
                    _name: str = tool_name,
                ) -> Any:
                    return await _call_mcp_tool(_url, _name, arguments)

                specs.append(
                    ToolSpec(
                        name=tool_name,
                        description=tool.description or "外部 MCP 查询工具",
                        json_schema=dict(tool.inputSchema or {"type": "object"}),
                        handler=handler,
                        source="mcp",
                        mcp_server=server_name,
                    )
                )
        except Exception as exc:
            # fail-open 仅表示跳过坏掉的外部只读工具；写工具永远不从未知 MCP 放行。
            logger.warning(
                "MCP Server 暂不可用，本轮跳过",
                extra={
                    "event": "mcp_discovery_failed",
                    "server": server_name,
                    "error": type(exc).__name__,
                },
            )
    return specs
