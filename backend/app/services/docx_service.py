from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


def build_translated_docx(translated_text: str, output_path: str, target_language: str = "ar") -> str:
    """Render translated text into a clean, formatted .docx file using python-docx."""
    document = Document()

    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(12)

    is_rtl = target_language.lower() in {"ar", "arabic", "he", "hebrew", "fa", "farsi", "ur", "urdu"}

    for raw_line in translated_text.split("\n"):
        line = raw_line.strip()
        paragraph = document.add_paragraph(line)
        if is_rtl:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            pf = paragraph.paragraph_format
            pf.right_to_left = True

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path
