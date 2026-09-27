"""PDF、Word、Excel 和 PowerPoint 文本加载器。"""

from pathlib import Path

from aidahelp.knowledge.models import LoadedDocument


def load_pdf(path: Path) -> LoadedDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"## 第 {index} 页\n\n{text}")
    return _loaded(path, "pdf", "\n\n".join(pages), {"page_count": len(reader.pages)})


def load_docx(path: Path) -> LoadedDocument:
    from docx import Document

    document = Document(str(path))
    blocks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table_index, table in enumerate(document.tables, start=1):
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        if rows:
            blocks.append(f"## 表格 {table_index}\n\n" + "\n".join(rows))
    return _loaded(path, "docx", "\n\n".join(blocks))


def load_xlsx(path: Path) -> LoadedDocument:
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets: list[str] = []
    try:
        for worksheet in workbook.worksheets:
            rows = []
            for row in worksheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value).strip() for value in row]
                if any(values):
                    rows.append(" | ".join(values))
            if rows:
                sheets.append(f"## 工作表：{worksheet.title}\n\n" + "\n".join(rows))
    finally:
        workbook.close()
    return _loaded(path, "xlsx", "\n\n".join(sheets), {"sheet_count": len(sheets)})


def load_pptx(path: Path) -> LoadedDocument:
    from pptx import Presentation

    presentation = Presentation(str(path))
    slides = []
    for index, slide in enumerate(presentation.slides, start=1):
        texts = []
        for shape in slide.shapes:
            text = getattr(shape, "text", "").strip()
            if text:
                texts.append(text)
        if texts:
            slides.append(f"## 第 {index} 页幻灯片\n\n" + "\n".join(texts))
    return _loaded(path, "pptx", "\n\n".join(slides), {"slide_count": len(presentation.slides)})


def _loaded(
    path: Path,
    source_type: str,
    content: str,
    metadata: dict[str, object] | None = None,
) -> LoadedDocument:
    return LoadedDocument(
        title=path.stem,
        source_type=source_type,
        source_uri=str(path.resolve()),
        content=content,
        metadata={"filename": path.name, **(metadata or {})},
    )
