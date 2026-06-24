from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings
from app.models.invoice import Invoice

settings = get_settings()

ARABIC_FONT_NAME = "NotoNaskhArabic"
_arabic_font_registered = False


def _ensure_arabic_font() -> str:
    """Register the bundled Arabic font with reportlab, falling back to Helvetica.

    Without a real Arabic-capable TTF at settings.ARABIC_FONT_PATH, Arabic text will
    not render with correct glyphs - add a font (e.g. Noto Naskh Arabic) at that path.
    """
    global _arabic_font_registered
    if _arabic_font_registered:
        return ARABIC_FONT_NAME

    font_path = Path(settings.ARABIC_FONT_PATH)
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(ARABIC_FONT_NAME, str(font_path)))
        _arabic_font_registered = True
        return ARABIC_FONT_NAME

    return "Helvetica"


def _ar(text: str) -> str:
    """Reshape + apply bidi algorithm so Arabic renders right-to-left and joined."""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


def build_invoice_pdf(invoice: Invoice, output_path: str) -> str:
    """Render a bilingual (Arabic + English) invoice PDF using reportlab (no LibreOffice)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    arabic_font = _ensure_arabic_font()

    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=18, spaceAfter=2)
    title_ar_style = ParagraphStyle(
        "TitleAr", parent=title_style, fontName=arabic_font, alignment=2  # right-aligned
    )
    normal = styles["Normal"]
    normal_ar = ParagraphStyle("NormalAr", parent=normal, fontName=arabic_font, alignment=2)

    elements = []

    elements.append(Paragraph(settings.COMPANY_NAME, title_style))
    elements.append(Paragraph(_ar(settings.COMPANY_NAME_AR), title_ar_style))
    elements.append(Paragraph(settings.COMPANY_EMAIL, normal))
    if settings.COMPANY_ADDRESS:
        elements.append(Paragraph(settings.COMPANY_ADDRESS, normal))
    elements.append(Spacer(1, 16))

    elements.append(Paragraph(f"<b>Invoice / {_ar('فاتورة')} #{invoice.number}</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Status / {_ar('الحالة')}: {invoice.status.value.upper()}", normal))
    elements.append(Paragraph(f"Issue date / {_ar('تاريخ الإصدار')}: {invoice.issue_date}", normal))
    if invoice.due_date:
        elements.append(Paragraph(f"Due date / {_ar('تاريخ الاستحقاق')}: {invoice.due_date}", normal))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"<b>Bill to / {_ar('فاتورة إلى')}:</b> {invoice.client.name}", normal))
    elements.append(Paragraph(invoice.client.email, normal))
    if invoice.client.address:
        elements.append(Paragraph(invoice.client.address, normal))
    elements.append(Spacer(1, 16))

    header = [
        f"Description / {_ar('الوصف')}",
        f"Qty / {_ar('الكمية')}",
        f"Unit Price / {_ar('سعر الوحدة')}",
        f"Total / {_ar('الإجمالي')}",
    ]
    table_data = [header]
    for item in invoice.items:
        table_data.append(
            [
                item.description,
                str(item.quantity),
                f"{item.unit_price:,.2f} {invoice.currency}",
                f"{item.quantity * item.unit_price:,.2f} {invoice.currency}",
            ]
        )

    table = Table(table_data, colWidths=[7.5 * cm, 2.5 * cm, 3.5 * cm, 3.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 16))

    totals_data = [
        [f"Subtotal / {_ar('الإجمالي الفرعي')}", f"{invoice.subtotal:,.2f} {invoice.currency}"],
        [
            f"Tax / {_ar('الضريبة')} ({invoice.tax_rate * 100:.0f}%)",
            f"{invoice.tax_amount:,.2f} {invoice.currency}",
        ],
        [f"Total / {_ar('الإجمالي')}", f"{invoice.total:,.2f} {invoice.currency}"],
    ]
    totals_table = Table(totals_data, colWidths=[13.5 * cm, 3.5 * cm])
    totals_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
            ]
        )
    )
    elements.append(totals_table)

    if invoice.notes:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"<b>Notes / {_ar('ملاحظات')}:</b> {invoice.notes}", normal))

    doc.build(elements)
    return output_path
