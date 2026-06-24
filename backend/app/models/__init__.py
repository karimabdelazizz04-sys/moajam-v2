# Import every model so app.db.base.Base.metadata is fully populated wherever
# this package is imported (Alembic autogenerate, app startup create_all, etc).
# Each model module imports Base from app.db.base - importing them here (and
# NOT from within app.db.base itself) avoids a circular import.
from app.models.user import User  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.translation_job import TranslationJob  # noqa: F401
from app.models.invoice import Invoice, InvoiceItem  # noqa: F401
from app.models.accounting import ChartOfAccount, JournalEntry, JournalLine  # noqa: F401
from app.models.erp import Notification, Project, Staff  # noqa: F401
