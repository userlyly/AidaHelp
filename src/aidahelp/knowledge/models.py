"""知识处理流水线中的普通数据对象。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    title: str
    source_type: str
    source_uri: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    chunk_index: int
    content: str
    section_path: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
