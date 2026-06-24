"""Create the first admin user for the accounting dashboard.

Usage (from the backend/ directory, inside the running container or venv):
    python -m scripts.create_admin <username> <password>
"""
import sys

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.create_admin <username> <password>")
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"User '{username}' already exists.")
            return
        user = User(username=username, hashed_password=hash_password(password), full_name=username)
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
