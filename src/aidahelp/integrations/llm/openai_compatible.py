"""OpenAI Chat Completions 兼容接口适配器。"""

import json
from typing import Any

import httpx

from aidahelp.integrations.llm.base import ChatMessage, ModelResponse, TokenUsage, ToolCall
from aidahelp.integrations.llm.errors import ChatModelUpstreamError


class OpenAICompatibleChatModel:
    """可连接 DeepSeek 或其他兼容 ``/chat/completions`` 的模型服务。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

    @property
    def name(self) -> str:
        return self._model

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> ModelResponse:
        serialized_messages = []
        for message in messages:
            item: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.name:
                item["name"] = message.name
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in message.tool_calls
                ]
            serialized_messages.append(item)
        payload = {
            "model": self._model,
            "messages": serialized_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            # 不使用开头的 /，这样 base_url 中已有的 /v1 不会被 httpx 丢弃。
            response = await self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            answer_message = data["choices"][0]["message"]
            content = answer_message.get("content") or ""
            raw_tool_calls = answer_message.get("tool_calls") or []
            if not content.strip() and not raw_tool_calls:
                raise ValueError("模型返回了空回答")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # 不把 API Key、完整请求或上游响应正文放进异常，避免日志泄露敏感数据。
            raise ChatModelUpstreamError("模型服务调用失败") from exc

        usage_data = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens"),
            completion_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens"),
        )
        tool_calls: list[ToolCall] = []
        for raw_call in raw_tool_calls:
            function = raw_call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except (TypeError, json.JSONDecodeError) as exc:
                raise ChatModelUpstreamError("模型工具参数不是合法 JSON") from exc
            if not isinstance(arguments, dict):
                raise ChatModelUpstreamError("模型工具参数不是 JSON 对象")
            tool_calls.append(
                ToolCall(
                    id=str(raw_call.get("id") or ""),
                    name=str(function.get("name") or ""),
                    arguments=arguments,
                )
            )
        return ModelResponse(
            content=content.strip(),
            model=str(data.get("model") or self._model),
            usage=usage,
            provider_request_id=response.headers.get("x-request-id") or data.get("id"),
            tool_calls=tool_calls,
        )

    async def close(self) -> None:
        await self._client.aclose()
