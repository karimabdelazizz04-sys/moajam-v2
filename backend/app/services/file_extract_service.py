from io import BytesIO
from pathlib import Path

import docx
from pypdf import PdfReader

# Below this many characters, a PDF is treated as scanned/image-only and routed
# through Claude Vision OCR instead of trusting the (empty) embedded text layer.
_MIN_PDF_TEXT_CHARS = 20


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
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if len(text.strip()) >= _MIN_PDF_TEXT_CHARS:
        return text
    # Empty/near-empty text layer -> the PDF is almost certainly scanned. Fall
    # back to rendering each page to an image and OCR'ing it with Claude Vision.
    return _ocr_pdf(path)


def _ocr_pdf(path: str) -> str:
    """Render each PDF page to a PNG and OCR it with Claude Vision.

    Lazy imports keep pdf2image/poppler off the hot path for normal text PDFs
    and avoid an import-time hard dependency. pdf2image needs the system
    `poppler-utils` package (installed in the Dockerfile).
    """
    from pdf2image import convert_from_path

    from app.services.claude_service import ocr_image

    images = convert_from_path(path, dpi=200)
    parts: list[str] = []
    for image in images:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        page_text = ocr_image(buffer.getvalue(), "image/png")
        if page_text.strip():
            parts.append(page_text)
    return "\n".join(parts)
