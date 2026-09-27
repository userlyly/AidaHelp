"""知识文本标准化。"""

import re
import unicodedata

_TRAILING_SPACES = re.compile(r"[ \t]+$", re.MULTILINE)
_EXCESSIVE_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """统一全半角、换行和空白，但不破坏 Markdown 标题及表格行。"""

    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _TRAILING_SPACES.sub("", normalized)
    normalized = _EXCESSIVE_BLANK_LINES.sub("\n\n", normalized)
    return normalized.strip()
