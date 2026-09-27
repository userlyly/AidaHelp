"""无需网络和 API Key 的教学用模型。"""

from aidahelp.integrations.llm.base import ChatMessage, ModelResponse, TokenUsage


class MockChatModel:
    """返回可预测答案，用于开发接口和数据库链路，不冒充真实智能模型。"""

    @property
    def name(self) -> str:
        return "mock-customer-service"

    async def generate(
        self,
        messages: list[ChatMessage],
        *,
        tools: list[dict] | None = None,
    ) -> ModelResponse:
        last_user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        content = (
            "这是 AidaHelp 的 Mock 回复。我已经收到你的问题："
            f"“{last_user_message}”。Mock 模式只验证工作流，不代表真实业务结论。"
        )
        return ModelResponse(
            content=content,
            model=self.name,
            usage=TokenUsage(),
            raw_metadata={"mock": True},
        )

    async def close(self) -> None:
        """Mock 没有网络连接，保留统一关闭接口方便应用装配。"""
