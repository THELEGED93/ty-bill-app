import sqlite3
from pathlib import Path
from datetime import datetime

# Find the database beside this script.
db_path = Path(__file__).resolve().parent / "bills.db"

if not db_path.exists():
    raise FileNotFoundError(f"Database not found: {db_path}")

backup_path = db_path.with_name(
    f"bills_backup_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
)

with sqlite3.connect(db_path) as conn:
    # Back up the existing database before changing anything.
    with sqlite3.connect(backup_path) as backup:
        conn.backup(backup)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("BEGIN")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL
        )
    """)

    for table in ("bills", "income"):
        columns = conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()

        column_names = [column[1] for column in columns]

        if "user_id" not in column_names:
            conn.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN user_id INTEGER REFERENCES users(id)
            """)

print(f"Backup saved: {backup_path.name}")
print("Account database structure added successfully.")