DROP TABLE IF EXISTS bills;

CREATE TABLE bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    frequency TEXT NOT NULL,
    notes TEXT,
    paid INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS income (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL,
    received_date TEXT NOT NULL
);