import sqlite3
from pathlib import Path
from datetime import datetime
from getpass import getpass
from werkzeug.security import check_password_hash

db_path = Path(__file__).resolve().parent / "bills.db"

if not db_path.exists():
    raise FileNotFoundError(f"Database not found: {db_path}")

email = input("Your MAIN account email: ").strip().lower()
password = getpass("Your main account password: ")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

try:
    conn.execute("PRAGMA foreign_keys = ON")

    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if user is None or not check_password_hash(
        user["password_hash"], password
    ):
        raise SystemExit("Email or password incorrect. Nothing changed.")

    backup_path = db_path.with_name(
        f"bills_backup_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    )

    with sqlite3.connect(backup_path) as backup:
        conn.backup(backup)

    conn.execute("BEGIN")

    bills_updated = conn.execute(
        "UPDATE bills SET user_id = ? WHERE user_id IS NULL",
        (user["id"],)
    ).rowcount

    income_updated = conn.execute(
        "UPDATE income SET user_id = ? WHERE user_id IS NULL",
        (user["id"],)
    ).rowcount

    conn.commit()

    print(f"Assigned to: {user['name']} ({user['email']})")
    print(f"Bills assigned: {bills_updated}")
    print(f"Income records assigned: {income_updated}")
    print(f"Backup saved: {backup_path.name}")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()