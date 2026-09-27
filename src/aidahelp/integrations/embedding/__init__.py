"""Embedding 模型统一接口。"""

from aidahelp.integrations.embedding.base import EmbeddingModel
from aidahelp.integrations.embedding.factory import build_embedding_model

__all__ = ["EmbeddingModel", "build_embedding_model"]
