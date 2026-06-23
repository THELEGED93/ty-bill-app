DROP TABLE IF EXISTS bills;

CREATE TABLE bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    frequency TEXT NOT NULL,
    notes TEXT
);