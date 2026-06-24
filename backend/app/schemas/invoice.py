from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.invoice import InvoiceStatus


class InvoiceItemIn(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float = 0.0


class InvoiceItemOut(InvoiceItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class InvoiceCreate(BaseModel):
    client_id: int
    currency: str = "EGP"
    issue_date: date | None = None
    due_date: date | None = None
    tax_rate: float = 0.0
    notes: str | None = None
    items: list[InvoiceItemIn]


class InvoiceUpdateStatus(BaseModel):
    status: InvoiceStatus


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    client_id: int
    status: InvoiceStatus
    currency: str
    issue_date: date
    due_date: date | None
    paid_at: datetime | None
    tax_rate: float
    notes: str | None
    items: list[InvoiceItemOut]
    subtotal: float
    tax_amount: float
    total: float
    created_at: datetime
