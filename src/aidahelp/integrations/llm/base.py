"""与具体厂商无关的聊天模型协议。"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """发给模型的一条标准消息。"""

    role: str
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """模型请求执行的结构化工具调用。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """一次模型调用消耗的 Token；Mock 或部分服务可能无法提供。"""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """屏蔽不同模型厂商返回格式后的统一结果。"""

    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    provider_request_id: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)


class ChatModel(Protocol):
    """ChatService 只依赖该协议，不直接依赖某个模型 SDK。"""

    @property
    def name(self) -> str: ...

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse: ...

    async def close(self) -> None: ...
