"""Markdown 和纯文本加载器。"""

import re
from pathlib import Path

from aidahelp.knowledge.models import LoadedDocument

_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def load_text(path: Path) -> LoadedDocument:
    content = path.read_text(encoding="utf-8-sig")
    title_match = _TITLE.search(content) if path.suffix.lower() == ".md" else None
    return LoadedDocument(
        title=title_match.group(1).strip() if title_match else path.stem,
        source_type=path.suffix.lower().lstrip("."),
        source_uri=str(path.resolve()),
        content=content,
        metadata={"filename": path.name},
    )
