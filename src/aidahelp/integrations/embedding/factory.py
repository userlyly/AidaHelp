"""根据配置创建 Embedding 模型。"""

from aidahelp.config import Settings
from aidahelp.integrations.embedding.base import EmbeddingModel
from aidahelp.integrations.embedding.errors import EmbeddingNotConfiguredError
from aidahelp.integrations.embedding.mock import HashEmbeddingModel
from aidahelp.integrations.embedding.openai_compatible import OpenAICompatibleEmbeddingModel


class UnconfiguredEmbeddingModel:
    def __init__(self, name: str, dimension: int) -> None:
        self._name = name
        self._dimension = dimension

    @property
    def name(self) -> str:
        return self._name

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise EmbeddingNotConfiguredError("缺少 AIDAHELP_EMBEDDING_API_KEY")

    async def embed_query(self, query: str) -> list[float]:
        del query
        raise EmbeddingNotConfiguredError("缺少 AIDAHELP_EMBEDDING_API_KEY")

    async def close(self) -> None:
        pass


def build_embedding_model(settings: Settings) -> EmbeddingModel:
    if settings.embedding_provider == "mock":
        return HashEmbeddingModel(settings.embedding_dimension)

    api_key = settings.embedding_api_key.get_secret_value() if settings.embedding_api_key else ""
    if not api_key.strip():
        return UnconfiguredEmbeddingModel(settings.embedding_model, settings.embedding_dimension)
    return OpenAICompatibleEmbeddingModel(
        base_url=settings.embedding_base_url,
        api_key=api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )
