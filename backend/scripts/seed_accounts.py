"""Seed a minimal default chart of accounts.

Usage (from the backend/ directory, inside the running container or venv):
    python -m scripts.seed_accounts
"""
from app.db.session import SessionLocal
from app.models.accounting import AccountType, ChartOfAccount

DEFAULT_ACCOUNTS = [
    ("1000", "Cash / Bank", AccountType.ASSET),
    ("1100", "Accounts Receivable", AccountType.ASSET),
    ("2000", "Accounts Payable", AccountType.LIABILITY),
    ("3000", "Owner's Equity", AccountType.EQUITY),
    ("4000", "Translation Revenue", AccountType.REVENUE),
    ("5000", "Translator/Reviewer Fees", AccountType.EXPENSE),
    ("5100", "Operating Expenses", AccountType.EXPENSE),
]


def main() -> None:
    db = SessionLocal()
    try:
        for code, name, account_type in DEFAULT_ACCOUNTS:
            if db.query(ChartOfAccount).filter(ChartOfAccount.code == code).first():
                continue
            db.add(ChartOfAccount(code=code, name=name, type=account_type))
        db.commit()
        print("Default chart of accounts seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
