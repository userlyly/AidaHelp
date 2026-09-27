"""保留章节路径的递归文本切块。"""

import math
import re

from aidahelp.knowledge.models import ChunkDraft, LoadedDocument
from aidahelp.knowledge.normalizer import normalize_text

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BOUNDARIES = ("\n\n", "。", "！", "？", ";", "；", "\n", "，", ",")


def split_document(
    document: LoadedDocument,
    *,
    chunk_size: int,
    overlap: int,
    category: str | None = None,
) -> list[ChunkDraft]:
    """先按 Markdown 标题识别章节，再在章节内部按自然边界切块。"""

    if overlap >= chunk_size:
        raise ValueError("chunk overlap 必须小于 chunk size")

    sections = _split_sections(normalize_text(document.content), document.title)
    drafts: list[ChunkDraft] = []
    for section_path, body in sections:
        for piece in _split_text(body, chunk_size=chunk_size, overlap=overlap):
            if not piece.strip():
                continue
            drafts.append(
                ChunkDraft(
                    chunk_index=len(drafts),
                    content=piece.strip(),
                    section_path=section_path,
                    # 中文通常约 1 个字对应 1~1.5 Token，这里只用于容量观测。
                    token_count=max(1, math.ceil(len(piece) / 1.2)),
                    metadata={
                        **document.metadata,
                        "category": category or document.metadata.get("category", "general"),
                    },
                )
            )
    return drafts


def _split_sections(text: str, fallback_title: str) -> list[tuple[str, str]]:
    heading_stack: list[str] = []
    sections: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            sections.append((" / ".join(heading_stack) or fallback_title, body))
        buffer.clear()

    for line in text.splitlines():
        match = _HEADING.match(line)
        if not match:
            buffer.append(line)
            continue
        flush()
        level = len(match.group(1))
        heading_stack[level - 1 :] = [match.group(2).strip()]
    flush()
    return sections or [(fallback_title, text)]


def _split_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(len(text), start + chunk_size)
        end = hard_end
        if hard_end < len(text):
            search_start = start + chunk_size // 2
            candidates = [text.rfind(mark, search_start, hard_end) for mark in _BOUNDARIES]
            best = max(candidates, default=-1)
            if best > start:
                end = best + 1
        pieces.append(text[start:end])
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return pieces
