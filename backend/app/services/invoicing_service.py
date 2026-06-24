import itertools
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.accounting import ChartOfAccount, JournalEntry, JournalLine
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.translation_job import TranslationJob

settings = get_settings()


def _next_invoice_number(db: Session) -> str:
    count = db.query(func.count(Invoice.id)).scalar() or 0
    for seq in itertools.count(count + 1):
        number = f"INV-{seq:05d}"
        if not db.query(Invoice).filter(Invoice.number == number).first():
            return number


def create_invoice_for_translation_job(db: Session, job: TranslationJob) -> Invoice | None:
    """Auto-generate a draft invoice once a translation job completes, if it has a client."""
    if not job.client_id:
        return None
    if job.invoice:
        return job.invoice

    invoice = Invoice(
        number=_next_invoice_number(db),
        client_id=job.client_id,
        translation_job_id=job.id,
        currency=settings.CURRENCY,
        issue_date=date.today(),
    )
    unit_price = job.price if job.price is not None else settings.DEFAULT_TRANSLATION_PRICE
    invoice.items = [
        InvoiceItem(
            description=f"Legal translation - {job.source_filename} "
            f"({job.source_language} -> {job.target_language})",
            quantity=1,
            unit_price=unit_price,
        )
    ]
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def post_invoice_payment_to_ledger(db: Session, invoice: Invoice) -> JournalEntry | None:
    """When an invoice is marked paid, post a Debit Cash / Credit Revenue journal entry.

    Silently skipped if the configured default accounts don't exist yet, so invoicing
    keeps working before the chart of accounts is fully set up.
    """
    cash_account = (
        db.query(ChartOfAccount).filter(ChartOfAccount.code == settings.ACCOUNTING_CASH_ACCOUNT_CODE).first()
    )
    revenue_account = (
        db.query(ChartOfAccount)
        .filter(ChartOfAccount.code == settings.ACCOUNTING_REVENUE_ACCOUNT_CODE)
        .first()
    )
    if not cash_account or not revenue_account:
        return None

    entry = JournalEntry(
        entry_date=(invoice.paid_at or datetime.utcnow()).date(),
        reference=invoice.number,
        description=f"Payment received for invoice {invoice.number}",
    )
    entry.lines = [
        JournalLine(account_id=cash_account.id, debit=invoice.total, credit=0.0, description=invoice.number),
        JournalLine(account_id=revenue_account.id, debit=0.0, credit=invoice.total, description=invoice.number),
    ]
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
