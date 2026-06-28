from flask import Flask, render_template, request, redirect, url_for 
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect("bills.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/bills", methods=["GET", "POST"])
def bills():
    if request.method == "POST":
        # save new bill logic
        return redirect(url_for("bills"))

    conn = get_db_connection()

    active_filter = request.args.get("status", "all")

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

    total = conn.execute(
        """
        SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) AS total
        FROM bills
        WHERE paid = 0
        """
    ).fetchone()["total"]

    conn.close()

    return render_template(
        "bills.html",
        bills=bills,
        total=total,
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