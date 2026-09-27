"""根据配置创建聊天模型。"""

from aidahelp.config import Settings
from aidahelp.integrations.llm.base import ChatModel
from aidahelp.integrations.llm.errors import ChatModelNotConfiguredError
from aidahelp.integrations.llm.mock import MockChatModel
from aidahelp.integrations.llm.openai_compatible import OpenAICompatibleChatModel


class UnconfiguredChatModel:
    """让 Web 服务可以正常启动，并在真正聊天时返回清晰的配置错误。"""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    @property
    def name(self) -> str:
        return self._model_name

    async def generate(self, messages: list[object]):
        del messages
        raise ChatModelNotConfiguredError("缺少 AIDAHELP_LLM_API_KEY")

    async def close(self) -> None:
        pass


def build_chat_model(settings: Settings) -> ChatModel:
    """模型选择集中在工厂中，业务代码不写 provider 判断。"""

    if settings.llm_provider == "mock":
        return MockChatModel()

    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
    if not api_key.strip():
        return UnconfiguredChatModel(settings.llm_model)

    return OpenAICompatibleChatModel(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )
