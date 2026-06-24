import itertools
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.client import Client
from app.models.erp import Notification
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceUpdateStatus
from app.services.invoice_pdf_service import build_invoice_pdf
from app.services.invoicing_service import post_invoice_payment_to_ledger
from app.services.wordpress_service import upload_media_to_wordpress

router = APIRouter(prefix="/invoices", tags=["invoices"], dependencies=[Depends(get_current_user)])


def _next_invoice_number(db: Session) -> str:
    count = db.query(func.count(Invoice.id)).scalar() or 0
    for seq in itertools.count(count + 1):
        number = f"INV-{seq:05d}"
        if not db.query(Invoice).filter(Invoice.number == number).first():
            return number


@router.get("", response_model=list[InvoiceOut])
def list_invoices(db: Session = Depends(get_db)):
    return db.query(Invoice).order_by(Invoice.created_at.desc()).all()


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)):
    client = db.get(Client, payload.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    invoice = Invoice(
        number=_next_invoice_number(db),
        client_id=payload.client_id,
        currency=payload.currency,
        issue_date=payload.issue_date or date.today(),
        due_date=payload.due_date,
        tax_rate=payload.tax_rate,
        notes=payload.notes,
    )
    invoice.items = [InvoiceItem(**item.model_dump()) for item in payload.items]

    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}/status", response_model=InvoiceOut)
def update_invoice_status(invoice_id: int, payload: InvoiceUpdateStatus, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    was_paid = invoice.status == InvoiceStatus.PAID
    invoice.status = payload.status
    if payload.status == InvoiceStatus.PAID and not was_paid:
        if invoice.paid_at is None:
            from datetime import datetime

            invoice.paid_at = datetime.utcnow()
        db.commit()
        db.refresh(invoice)
        post_invoice_payment_to_ledger(db, invoice)
        if invoice.translation_job and invoice.translation_job.created_by:
            db.add(
                Notification(
                    recipient=invoice.translation_job.created_by,
                    type="invoice_paid",
                    message=f"Invoice {invoice.number} marked as paid.",
                    related_invoice_id=invoice.id,
                )
            )
            db.commit()
    else:
        db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/pdf", response_model=InvoiceOut)
def generate_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    """Render the invoice to PDF in a scratch temp file, push it straight to
    the WordPress Media Library, then discard the local copy - Render keeps
    no durable file of its own.
    """
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        build_invoice_pdf(invoice, tmp_path)
        pdf_bytes = Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    media = upload_media_to_wordpress(pdf_bytes, f"{invoice.number}.pdf", "application/pdf")

    invoice.pdf_url = media["url"]
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/{invoice_id}/download")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)):
    """The invoice PDF lives on WordPress, not on Render - redirect there."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not invoice.pdf_url:
        raise HTTPException(status_code=404, detail="PDF not generated yet")
    return RedirectResponse(invoice.pdf_url)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(invoice)
    db.commit()
