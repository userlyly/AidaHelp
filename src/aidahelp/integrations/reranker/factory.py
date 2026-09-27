"""根据配置创建精排器。"""

from aidahelp.config import Settings
from aidahelp.integrations.reranker.base import Reranker
from aidahelp.integrations.reranker.errors import RerankerNotConfiguredError
from aidahelp.integrations.reranker.mock import LexicalReranker
from aidahelp.integrations.reranker.openai_compatible import OpenAICompatibleReranker


class UnconfiguredReranker:
    @property
    def name(self) -> str:
        return "unconfigured"

    async def rerank(
        self, query: str, documents: list[str], *, top_n: int
    ) -> list[tuple[int, float]]:
        del query, documents, top_n
        raise RerankerNotConfiguredError("缺少 AIDAHELP_RERANK_API_KEY")

    async def close(self) -> None:
        pass


def build_reranker(settings: Settings) -> Reranker:
    if settings.rerank_provider == "mock":
        return LexicalReranker()
    api_key = settings.rerank_api_key.get_secret_value() if settings.rerank_api_key else ""
    if not api_key.strip():
        return UnconfiguredReranker()
    return OpenAICompatibleReranker(
        base_url=settings.rerank_base_url,
        api_key=api_key,
        model=settings.rerank_model,
        timeout_seconds=settings.rerank_timeout_seconds,
    )
