from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort, session
)
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

import sqlite3
import os
from pathlib import Path
from datetime import date, datetime

app = Flask(__name__)

# Keep Azure runtime data outside the temporary deployment directory.
# Local development continues using bills.db beside this file.
is_azure = bool(os.environ.get("WEBSITE_SITE_NAME"))
data_dir = Path(os.environ.get("TYBILL_DATA_DIR") or (
    "/home/tybill-data" if is_azure else app.root_path
)).expanduser().resolve()
data_dir.mkdir(parents=True, exist_ok=True)
app.config["DATABASE"] = str(data_dir / "bills.db")

secret_path = (
    data_dir / "secret_key" if is_azure or os.environ.get("TYBILL_DATA_DIR")
    else Path(app.instance_path) / "secret_key"
)
if os.environ.get("SECRET_KEY"):
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
else:
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids replacing a key already on disk.
    try:
        with secret_path.open("x", encoding="utf-8") as key_file:
            key_file.write(os.urandom(32).hex())
    except FileExistsError:
        pass
    app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8").strip()

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Set up login management.
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Prepare form protection; we'll activate it after updating the forms.
csrf = CSRFProtect()
csrf.init_app(app)

def get_db_connection():
    conn = sqlite3.connect(app.config["DATABASE"], timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn 

def initialize_database():
    """Create missing tables; never drop tables or replace existing records."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor TEXT NOT NULL,
                    amount REAL NOT NULL,
                    due_date TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    notes TEXT,
                    category TEXT,
                    paid INTEGER NOT NULL DEFAULT 0,
                    user_id INTEGER REFERENCES users(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS income (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    amount REAL NOT NULL,
                    frequency TEXT NOT NULL,
                    received_date TEXT,
                    user_id INTEGER REFERENCES users(id)
                )
            """)
    finally:
        conn.close()


# Gunicorn imports this module, so initialization must be outside __main__.
initialize_database()


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]


@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    conn = get_db_connection()

    try:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()

    return User(row) if row else None

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("bills"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()

        try:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        if row is None or not check_password_hash(
            row["password_hash"], password
        ):
            flash("Incorrect email or password.")
            return render_template("login.html")

        # Clear any previous session before signing in.
        session.clear()
        login_user(User(row))

        return redirect(url_for("bills"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("bills"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or len(name) > 100:
            flash("Enter a name between 1 and 100 characters.")
            return render_template("register.html")

        if (
            len(email) > 254
            or email.count("@") != 1
            or not email.split("@")[0]
            or "." not in email.split("@")[-1]
            or any(character.isspace() for character in email)
        ):
            flash("Enter a valid email address.")
            return render_template("register.html")

        if not 12 <= len(password) <= 128:
            flash("Use a password between 12 and 128 characters.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Your passwords do not match.")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        conn = get_db_connection()

        try:
            conn.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (name, email, password_hash)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Unable to register with that email. Try logging in.")
            return render_template("register.html")
        finally:
            conn.close()

        flash("Account created. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/bills", methods=["GET", "POST"])
@login_required
def bills():
    if request.method == "POST":
        vendor = request.form.get("vendor")
        amount = request.form.get("amount")
        due_date = request.form.get("due_date")
        frequency = request.form.get("frequency")
        notes = request.form.get("notes")
        category = request.form.get("category")


        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO bills (
                vendor, amount, due_date, frequency,
                notes, category, paid, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vendor, amount, due_date, frequency,
                notes, category, 0, current_user.id
            )
        )

        conn.commit()
        conn.close()

        return redirect(url_for("bills"))

    conn = get_db_connection()
    
    active_filter = request.args.get("status", "all")

    # Show only this user's bills, based on the selected filter.
    if active_filter == "paid":
        bills = conn.execute(
            """
            SELECT * FROM bills
            WHERE user_id = ? AND paid = 1
            ORDER BY due_date ASC
            """,
            (current_user.id,)
        ).fetchall()

    elif active_filter == "unpaid":
        bills = conn.execute(
            """
            SELECT * FROM bills
            WHERE user_id = ? AND (paid = 0 OR paid IS NULL)
            ORDER BY due_date ASC
            """,
            (current_user.id,)
        ).fetchall()

    else:
        bills = conn.execute(
            """
            SELECT * FROM bills
            WHERE user_id = ?
            ORDER BY due_date ASC
            """,
            (current_user.id,)
        ).fetchall()

    # Dashboard totals include all bills belonging to this user.
    all_bills = conn.execute(
        """
        SELECT * FROM bills
        WHERE user_id = ?
        ORDER BY due_date ASC
        """,
        (current_user.id,)
    ).fetchall()

    income_rows = conn.execute(
        """
        SELECT id, source, amount, frequency
        FROM income
        WHERE user_id = ?
        ORDER BY source
        """,
        (current_user.id,)
    ).fetchall()

    monthly_income = 0

    for income in income_rows:
        amount = float(income["amount"])
        frequency = income["frequency"].lower()

        if frequency == "weekly":
            monthly_income += amount * 52 / 12

        elif frequency == "biweekly":
            monthly_income += amount * 26 / 12

        elif frequency == "twice-monthly":
            monthly_income += amount * 2

        elif frequency == "yearly" or frequency == "annual":
            monthly_income += amount / 12

        else:
            monthly_income += amount

    total_due = 0
    total_unpaid = 0

    for bill in all_bills:
        amount = float(bill["amount"])
        frequency = bill["frequency"].lower()
        paid = bill["paid"]

        if frequency == "weekly":
            monthly_amount = amount * 4
        elif frequency == "biweekly":
            monthly_amount = amount * 2
        elif frequency == "yearly" or frequency == "annual":
            monthly_amount = amount / 12
        else:
            monthly_amount = amount

        total_due += monthly_amount

        if paid == 0 or paid is None:
            total_unpaid += monthly_amount

    left_after_bills = monthly_income - total_due

    bill_list = []

    for bill in bills:
        bill_data = dict(bill)

        if bill_data["paid"] == 1:
            bill_data["display_status"] = "Paid"

        else:
            bill_due_date = datetime.strptime(
                bill_data["due_date"],
                "%Y-%m-%d"
            ).date()

            days_until_due = (
                bill_due_date - date.today()
            ).days

            if days_until_due < 0:
                bill_data["display_status"] = "Overdue"

            elif days_until_due <= 7:
                bill_data["display_status"] = "Due Soon"

            else:
                bill_data["display_status"] = "Unpaid"

        bill_list.append(bill_data)

    conn.close()

    return render_template(
        "bills.html",
        bills=bill_list,
        incomes=income_rows,
        monthly_income=monthly_income,
        total_due=total_due,
        total_unpaid=total_unpaid,
        left_after_bills=left_after_bills,
        active_filter=active_filter
    )

@app.route("/delete/<int:bill_id>", methods=["POST"])
@login_required
def delete_bill(bill_id):
    conn = get_db_connection()

    try:
        result = conn.execute(
            "DELETE FROM bills WHERE id = ? AND user_id = ?",
            (bill_id, current_user.id)
        )

        if result.rowcount == 0:
            abort(404)

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("bills"))

@app.route("/toggle_paid_status/<int:bill_id>", methods=["POST"])
@login_required
def toggle_paid_status(bill_id):
    conn = get_db_connection()

    try:
        result = conn.execute(
            """
            UPDATE bills
            SET paid = CASE WHEN paid = 1 THEN 0 ELSE 1 END
            WHERE id = ? AND user_id = ?
            """,
            (bill_id, current_user.id)
        )

        if result.rowcount == 0:
            abort(404)

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("bills"))

@app.route("/edit/<int:bill_id>", methods=["GET", "POST"])
@login_required
def edit_bill(bill_id):
    conn = get_db_connection()

    try:
        bill = conn.execute(
            "SELECT * FROM bills WHERE id = ? AND user_id = ?",
            (bill_id, current_user.id)
        ).fetchone()

        if bill is None:
            abort(404)

        if request.method == "POST":
            vendor = request.form["vendor"]
            amount = request.form["amount"]
            due_date = request.form["due_date"]
            frequency = request.form["frequency"]
            notes = request.form["notes"]
            category = request.form["category"]

            conn.execute(
                """
                UPDATE bills
                SET vendor = ?, amount = ?, due_date = ?,
                    frequency = ?, notes = ?, category = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    vendor, amount, due_date,
                    frequency, notes, category,
                    bill_id, current_user.id
                )
            )

            conn.commit()
            return redirect(url_for("bills"))

        return render_template("edit_bill.html", bill=bill)

    finally:
        conn.close()

@app.route("/income/add", methods=["POST"])
@login_required
def add_income():
    source = request.form["source"]
    amount = float(request.form["amount"])
    frequency = request.form["frequency"]
    received_date = request.form.get("received_date") or None

    conn = get_db_connection()

    try:
        conn.execute(
            """
            INSERT INTO income (
                source, amount, frequency, received_date, user_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source, amount, frequency,
                received_date, current_user.id
            )
        )

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("bills"))

@app.route("/income/edit/<int:income_id>", methods=["POST"])
@login_required
def edit_income(income_id):
    conn = get_db_connection()

    try:
        income = conn.execute(
            "SELECT id FROM income WHERE id = ? AND user_id = ?",
            (income_id, current_user.id)
        ).fetchone()

        if income is None:
            abort(404)

        source = request.form["source"]
        amount = float(request.form["amount"])
        frequency = request.form["frequency"]

        conn.execute(
            """
            UPDATE income
            SET source = ?, amount = ?, frequency = ?
            WHERE id = ? AND user_id = ?
            """,
            (source, amount, frequency, income_id, current_user.id)
        )

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("bills"))


@app.route("/income/delete/<int:income_id>", methods=["POST"])
@login_required
def delete_income(income_id):
    conn = get_db_connection()

    try:
        result = conn.execute(
            "DELETE FROM income WHERE id = ? AND user_id = ?",
            (income_id, current_user.id)
        )

        if result.rowcount == 0:
            abort(404)

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for("bills"))

if __name__ == "__main__":
    app.run(debug=False)