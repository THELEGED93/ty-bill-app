from flask import Flask, render_template, request, redirect, url_for 
import sqlite3
from datetime import date,datetime
app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("bills.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/bills", methods=["GET", "POST"])
def bills():
    if request.method == "POST":
        vendor = request.form.get("vendor")
        amount = request.form.get("amount")
        due_date = request.form.get("due_date")
        frequency = request.form.get("frequency")
        notes = request.form.get("notes")

        print("FORM DATA:", request.form)

        conn = get_db_connection()

        conn.execute(
            """
            INSERT INTO bills (vendor, amount, due_date, frequency, notes, paid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (vendor, amount, due_date, frequency, notes, 0)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("bills"))

    conn = get_db_connection()
    
    active_filter = request.args.get("status", "all")

    # Bills shown in the table, based on filter
    if active_filter == "paid":
        bills = conn.execute(
            "SELECT * FROM bills WHERE paid = 1 ORDER BY due_date ASC"
        ).fetchall()

    elif active_filter == "unpaid":
        bills = conn.execute(
            """
            SELECT * FROM bills
            WHERE paid = 0 OR paid IS NULL
            ORDER BY due_date ASC
            """
        ).fetchall()

    else:
        bills = conn.execute(
            "SELECT * FROM bills ORDER BY due_date ASC"
        ).fetchall()

    # Use ALL bills for dashboard totals, not just filtered bills
    all_bills = conn.execute(
        "SELECT * FROM bills ORDER BY due_date ASC"
    ).fetchall()

    monthly_income = 3127.00

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
        monthly_income=monthly_income,
        total_due=total_due,
        total_unpaid=total_unpaid,
        left_after_bills=left_after_bills,
        active_filter=active_filter
    )

@app.route("/delete/<int:bill_id>", methods=["POST"])
def delete_bill(bill_id):
    conn = get_db_connection()

    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("bills"))

@app.route("/toggle_paid_status/<int:bill_id>", methods=["POST"])
def toggle_paid_status(bill_id):
    conn = get_db_connection()

    bill = conn.execute(
        "SELECT paid FROM bills WHERE id = ?",
        (bill_id,)
    ).fetchone()

    new_paid_status = 0 if bill["paid"] else 1

    print("Old paid status:", bill["paid"])
    print("New paid status:", new_paid_status)

    conn.execute(
        "UPDATE bills SET paid = ? WHERE id = ?",
        (new_paid_status, bill_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("bills"))

@app.route("/edit/<int:bill_id>", methods=["GET", "POST"])
def edit_bill(bill_id):
    conn = get_db_connection()

    if request.method == "POST":
        vendor = request.form["vendor"]
        amount = request.form["amount"]
        due_date = request.form["due_date"]
        frequency = request.form["frequency"]
        notes = request.form["notes"]

        conn.execute(
            """
            UPDATE bills
            SET vendor = ?, amount = ?, due_date = ?, frequency = ?, notes = ?
            WHERE id = ?
            """,
            (vendor, amount, due_date, frequency, notes, bill_id)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("bills"))

    bill = conn.execute(
        "SELECT * FROM bills WHERE id = ?",
        (bill_id,)
    ).fetchone()

    conn.close()

    return render_template("edit_bill.html", bill=bill)
if __name__ == "__main__":
    app.run(debug=True)