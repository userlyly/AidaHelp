"""Embedding 适配层异常。"""


class EmbeddingError(Exception):
    pass


class EmbeddingNotConfiguredError(EmbeddingError):
    pass


class EmbeddingUpstreamError(EmbeddingError):
    pass
