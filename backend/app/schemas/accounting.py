from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.accounting import AccountType


class AccountCreate(BaseModel):
    code: str
    name: str
    type: AccountType
    parent_id: int | None = None
    is_active: bool = True


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    type: AccountType
    parent_id: int | None
    is_active: bool
    created_at: datetime


class AccountBalanceOut(AccountOut):
    balance: float


class JournalLineIn(BaseModel):
    account_id: int
    description: str | None = None
    debit: float = 0.0
    credit: float = 0.0


class JournalLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    description: str | None
    debit: float
    credit: float


class JournalEntryCreate(BaseModel):
    entry_date: date | None = None
    reference: str | None = None
    description: str | None = None
    lines: list[JournalLineIn]

    @model_validator(mode="after")
    def _validate_balanced(self):
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if round(total_debit, 2) != round(total_credit, 2):
            raise ValueError(
                f"Journal entry is not balanced: debit={total_debit:.2f} credit={total_credit:.2f}"
            )
        return self


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    reference: str | None
    description: str | None
    lines: list[JournalLineOut]
    total_debit: float
    total_credit: float
    created_at: datetime


class ProfitAndLossLine(BaseModel):
    account_id: int
    code: str
    name: str
    amount: float


class ProfitAndLossOut(BaseModel):
    start_date: date
    end_date: date
    revenue: list[ProfitAndLossLine]
    expenses: list[ProfitAndLossLine]
    total_revenue: float
    total_expenses: float
    net_income: float


class BalanceSheetLine(BaseModel):
    account_id: int
    code: str
    name: str
    balance: float


class BalanceSheetOut(BaseModel):
    as_of: date
    assets: list[BalanceSheetLine]
    liabilities: list[BalanceSheetLine]
    equity: list[BalanceSheetLine]
    total_assets: float
    total_liabilities: float
    total_equity: float
