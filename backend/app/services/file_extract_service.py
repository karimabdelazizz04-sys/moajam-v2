from pathlib import Path

import docx
from pypdf import PdfReader


class UnsupportedFileType(Exception):
    pass


def extract_text(path: str) -> str:
    """Extract raw text from an uploaded .docx, .pdf or .txt file."""
    suffix = Path(path).suffix.lower()

    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".txt":
        return Path(path).read_text(encoding="utf-8", errors="ignore")

    raise UnsupportedFileType(f"Unsupported file type: {suffix}")


def _extract_docx(path: str) -> str:
    document = docx.Document(path)
    parts: list[str] = []

    for para in document.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def _extract_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)
