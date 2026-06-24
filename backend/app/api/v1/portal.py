from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.models.client import Client
from app.models.invoice import Invoice
from app.schemas.client import ClientOut
from app.schemas.invoice import InvoiceOut

router = APIRouter(prefix="/portal", tags=["portal"], dependencies=[Depends(verify_api_key)])


@router.get("/clients/lookup", response_model=ClientOut | None)
def lookup_client_by_email(email: str, db: Session = Depends(get_db)):
    return db.query(Client).filter(Client.email == email).first()


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices_for_portal(
    client_id: int | None = None,
    client_email: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Invoice)
    if client_email:
        client = db.query(Client).filter(Client.email == client_email).first()
        if not client:
            return []
        client_id = client.id
    if client_id:
        query = query.filter(Invoice.client_id == client_id)
    return query.order_by(Invoice.created_at.desc()).all()


@router.get("/invoices/{invoice_id}/download")
def download_invoice_for_portal(invoice_id: int, db: Session = Depends(get_db)):
    """The invoice PDF lives on WordPress, not on Render - redirect there."""
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not invoice.pdf_url:
        raise HTTPException(status_code=404, detail="PDF not generated yet")
    return RedirectResponse(invoice.pdf_url)
