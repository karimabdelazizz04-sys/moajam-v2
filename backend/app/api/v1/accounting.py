from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.accounting import AccountType, ChartOfAccount, JournalEntry, JournalLine
from app.schemas.accounting import (
    AccountCreate,
    AccountOut,
    BalanceSheetLine,
    BalanceSheetOut,
    JournalEntryCreate,
    JournalEntryOut,
    ProfitAndLossLine,
    ProfitAndLossOut,
)

router = APIRouter(prefix="/accounting", tags=["accounting"], dependencies=[Depends(get_current_user)])

CREDIT_NORMAL_TYPES = {AccountType.LIABILITY, AccountType.EQUITY, AccountType.REVENUE}


# ---------------------------------------------------------------------------
# Chart of accounts
# ---------------------------------------------------------------------------


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(ChartOfAccount).order_by(ChartOfAccount.code).all()


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    if db.query(ChartOfAccount).filter(ChartOfAccount.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Account code already exists")
    account = ChartOfAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.get(ChartOfAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.lines:
        raise HTTPException(status_code=400, detail="Cannot delete an account with journal lines")
    db.delete(account)
    db.commit()


# ---------------------------------------------------------------------------
# Journal entries
# ---------------------------------------------------------------------------


@router.get("/journal-entries", response_model=list[JournalEntryOut])
def list_journal_entries(db: Session = Depends(get_db)):
    return db.query(JournalEntry).order_by(JournalEntry.entry_date.desc()).all()


@router.post("/journal-entries", response_model=JournalEntryOut, status_code=201)
def create_journal_entry(payload: JournalEntryCreate, db: Session = Depends(get_db)):
    account_ids = {line.account_id for line in payload.lines}
    existing = {a.id for a in db.query(ChartOfAccount.id).filter(ChartOfAccount.id.in_(account_ids)).all()}
    missing = account_ids - existing
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown account ids: {sorted(missing)}")

    entry = JournalEntry(
        entry_date=payload.entry_date or date.today(),
        reference=payload.reference,
        description=payload.description,
    )
    entry.lines = [JournalLine(**line.model_dump()) for line in payload.lines]
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/journal-entries/{entry_id}", response_model=JournalEntryOut)
def get_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return entry


@router.delete("/journal-entries/{entry_id}", status_code=204)
def delete_journal_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    db.delete(entry)
    db.commit()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _account_movement(db: Session, account_type: AccountType, start: date | None, end: date | None):
    """Return (account, signed_amount) for every account of the given type, net of debit/credit."""
    query = (
        db.query(
            ChartOfAccount,
            func.coalesce(func.sum(JournalLine.debit), 0.0),
            func.coalesce(func.sum(JournalLine.credit), 0.0),
        )
        .outerjoin(JournalLine, JournalLine.account_id == ChartOfAccount.id)
        .outerjoin(JournalEntry, JournalEntry.id == JournalLine.entry_id)
        .filter(ChartOfAccount.type == account_type)
    )
    if start is not None:
        query = query.filter((JournalEntry.entry_date.is_(None)) | (JournalEntry.entry_date >= start))
    if end is not None:
        query = query.filter((JournalEntry.entry_date.is_(None)) | (JournalEntry.entry_date <= end))

    results = []
    for account, total_debit, total_credit in query.group_by(ChartOfAccount.id):
        if account_type in CREDIT_NORMAL_TYPES:
            amount = total_credit - total_debit
        else:
            amount = total_debit - total_credit
        results.append((account, amount))
    return results


@router.get("/reports/profit-and-loss", response_model=ProfitAndLossOut)
def profit_and_loss(
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
):
    revenue = [
        ProfitAndLossLine(account_id=a.id, code=a.code, name=a.name, amount=amount)
        for a, amount in _account_movement(db, AccountType.REVENUE, start_date, end_date)
    ]
    expenses = [
        ProfitAndLossLine(account_id=a.id, code=a.code, name=a.name, amount=amount)
        for a, amount in _account_movement(db, AccountType.EXPENSE, start_date, end_date)
    ]
    total_revenue = sum(line.amount for line in revenue)
    total_expenses = sum(line.amount for line in expenses)
    return ProfitAndLossOut(
        start_date=start_date,
        end_date=end_date,
        revenue=revenue,
        expenses=expenses,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_income=total_revenue - total_expenses,
    )


@router.get("/reports/balance-sheet", response_model=BalanceSheetOut)
def balance_sheet(as_of: date, db: Session = Depends(get_db)):
    assets = [
        BalanceSheetLine(account_id=a.id, code=a.code, name=a.name, balance=amount)
        for a, amount in _account_movement(db, AccountType.ASSET, None, as_of)
    ]
    liabilities = [
        BalanceSheetLine(account_id=a.id, code=a.code, name=a.name, balance=amount)
        for a, amount in _account_movement(db, AccountType.LIABILITY, None, as_of)
    ]
    equity = [
        BalanceSheetLine(account_id=a.id, code=a.code, name=a.name, balance=amount)
        for a, amount in _account_movement(db, AccountType.EQUITY, None, as_of)
    ]
    return BalanceSheetOut(
        as_of=as_of,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        total_assets=sum(line.balance for line in assets),
        total_liabilities=sum(line.balance for line in liabilities),
        total_equity=sum(line.balance for line in equity),
    )
