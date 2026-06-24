from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import all models here so Alembic autogenerate can discover them.
from app.models.user import User  # noqa: E402,F401
from app.models.client import Client  # noqa: E402,F401
from app.models.translation_job import TranslationJob  # noqa: E402,F401
from app.models.invoice import Invoice, InvoiceItem  # noqa: E402,F401
from app.models.accounting import ChartOfAccount, JournalEntry, JournalLine  # noqa: E402,F401
