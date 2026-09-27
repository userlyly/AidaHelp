"""根据文件扩展名选择加载器。"""

from collections.abc import Callable
from pathlib import Path

from aidahelp.knowledge.loaders.office import load_docx, load_pdf, load_pptx, load_xlsx
from aidahelp.knowledge.loaders.text import load_text
from aidahelp.knowledge.models import LoadedDocument

Loader = Callable[[Path], LoadedDocument]
_LOADERS: dict[str, Loader] = {
    ".md": load_text,
    ".txt": load_text,
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".xlsx": load_xlsx,
    ".pptx": load_pptx,
}


def supported_extensions() -> set[str]:
    return set(_LOADERS)


def load_document(path: str | Path) -> LoadedDocument:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"知识文件不存在：{resolved}")
    loader = _LOADERS.get(resolved.suffix.lower())
    if loader is None:
        raise ValueError(f"不支持的知识文件格式：{resolved.suffix}")
    document = loader(resolved)
    if not document.content.strip():
        raise ValueError(f"没有从文件中解析出文本：{resolved}")
    return document
