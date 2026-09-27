"""与工具来源无关的统一描述对象。"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from aidahelp.domain.enums import ToolPermission


@dataclass(slots=True)
class ToolContext:
    session: AsyncSession
    user_id: str
    conversation_id: str


ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[Any]]


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    json_schema: dict[str, Any]
    handler: ToolHandler
    permission: ToolPermission = ToolPermission.READ
    source: Literal["builtin", "mcp"] = "builtin"
    mcp_server: str | None = None
    timeout_seconds: float | None = None
    max_retries: int | None = None

    def model_schema(self) -> dict[str, Any]:
        """转换成 OpenAI-compatible Function Calling 所需的 tools 结构。"""

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.json_schema,
            },
        }
