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
        # Handle form submission
        vendor = request.form["vendor"]
        amount = request.form["amount"]
        due_date = request.form["due_date"]
        frequency = request.form["frequency"]
        notes = request.form["notes"]

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO bills (vendor, amount, due_date, frequency, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (vendor, amount, due_date, frequency, notes)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("bills"))
    
    conn = get_db_connection()
    bills = conn.execute("SELECT * FROM bills").fetchall()
    conn.close()

    return render_template("bills.html", bills=bills)

@app.route("/delete/<int:bill_id>", methods=["POST"])
def delete_bill(bill_id):
    conn = get_db_connection()

    conn.execute("DELETE FROM bills WHERE id = ?", (bill_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("bills"))

if __name__ == "__main__":
    app.run(debug=True)