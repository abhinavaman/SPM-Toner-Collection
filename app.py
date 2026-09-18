from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
import csv
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DB = "toner.db"


# -------------------------------------------------
# DATABASE CONNECTION
# -------------------------------------------------

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------
# CREATE DATABASE TABLES
# -------------------------------------------------

def init_db():

    conn = db()

    # Employee master table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_master (
            employee_code TEXT PRIMARY KEY,
            employee_name TEXT NOT NULL,
            department TEXT NOT NULL
        )
    """)

    # Toner collection table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS toner_collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            department TEXT NOT NULL,
            printer_name TEXT NOT NULL,
            toner_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            collection_date TEXT NOT NULL,
            remarks TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Sample employees for testing
    sample_employees = [
        ("EMP001", "Rahul Sharma", "IT"),
        ("EMP002", "Priya Verma", "HR"),
        ("EMP003", "Amit Kumar", "Finance"),
        ("EMP004", "Neha Singh", "Production"),
        ("EMP005", "Rohit Das", "Maintenance")
    ]

    conn.executemany("""
        INSERT OR IGNORE INTO employee_master
        (employee_code, employee_name, department)
        VALUES (?, ?, ?)
    """, sample_employees)

    conn.commit()
    conn.close()


# -------------------------------------------------
# HOME PAGE
# -------------------------------------------------

@app.route("/")
def home():

    search = request.args.get("search", "").strip()

    conn = db()

    # Search records
    if search:

        rows = conn.execute("""
            SELECT * FROM toner_collection
            WHERE employee_name LIKE ?
               OR employee_id LIKE ?
               OR department LIKE ?
               OR printer_name LIKE ?
               OR toner_type LIKE ?
            ORDER BY id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        )).fetchall()

    else:

        rows = conn.execute("""
            SELECT *
            FROM toner_collection
            ORDER BY id DESC
        """).fetchall()

    # Total records
    total = conn.execute("""
        SELECT COUNT(*) c
        FROM toner_collection
    """).fetchone()["c"]

    # Unique employees
    people = conn.execute("""
        SELECT COUNT(DISTINCT employee_id) c
        FROM toner_collection
    """).fetchone()["c"]

    # Get departments for export dropdown
    departments = conn.execute("""
        SELECT DISTINCT department
        FROM employee_master
        WHERE department IS NOT NULL
        AND department != ''
        ORDER BY department
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        rows=rows,
        total=total,
        people=people,
        search=search,
        departments=departments
    )


# -------------------------------------------------
# GET EMPLOYEE DETAILS
# -------------------------------------------------

@app.get("/employee/<employee_code>")
def get_employee(employee_code):

    conn = db()

    employee = conn.execute("""
        SELECT employee_code, employee_name, department
        FROM employee_master
        WHERE employee_code = ?
    """, (employee_code.strip(),)).fetchone()

    conn.close()

    if employee:

        return jsonify({
            "found": True,
            "employee_code": employee["employee_code"],
            "employee_name": employee["employee_name"],
            "department": employee["department"]
        })

    return jsonify({
        "found": False
    })


# -------------------------------------------------
# SUBMIT TONER COLLECTION
# -------------------------------------------------

@app.post("/submit")
def submit():

    fields = [
        "employee_id",
        "printer_name",
        "toner_type",
        "quantity",
        "collection_date"
    ]

    # Check required fields
    if any(not request.form.get(f, "").strip() for f in fields):

        flash(
            "Please fill all required fields.",
            "error"
        )

        return redirect(url_for("home"))

    employee_id = request.form["employee_id"].strip()

    conn = db()

    # Find employee
    employee = conn.execute("""
        SELECT employee_name, department
        FROM employee_master
        WHERE employee_code = ?
    """, (employee_id,)).fetchone()

    # Employee not found
    if not employee:

        conn.close()

        flash(
            "Employee code not found.",
            "error"
        )

        return redirect(url_for("home"))

    # Validate quantity
    try:

        quantity = int(
            request.form["quantity"]
        )

        if quantity < 1:
            raise ValueError

    except ValueError:

        conn.close()

        flash(
            "Quantity must be a positive number.",
            "error"
        )

        return redirect(url_for("home"))

    # Save toner collection record
    conn.execute("""
        INSERT INTO toner_collection
        (
            employee_name,
            employee_id,
            department,
            printer_name,
            toner_type,
            quantity,
            collection_date,
            remarks,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        employee["employee_name"],
        employee_id,
        employee["department"],
        request.form["printer_name"].strip(),
        request.form["toner_type"].strip(),
        quantity,
        request.form["collection_date"],
        request.form.get("remarks", "").strip(),
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    ))

    conn.commit()
    conn.close()

    flash(
        "Record saved successfully.",
        "success"
    )

    return redirect(url_for("home"))


# -------------------------------------------------
# EXPORT CSV
# -------------------------------------------------

@app.get("/export")
def export():

    # Get filters
    start_date = request.args.get(
        "start_date",
        ""
    ).strip()

    end_date = request.args.get(
        "end_date",
        ""
    ).strip()

    department = request.args.get(
        "department",
        ""
    ).strip()

    conn = db()

    # Base query
    query = """
        SELECT *
        FROM toner_collection
        WHERE 1=1
    """

    params = []

    # Start date filter
    if start_date:

        query += """
            AND collection_date >= ?
        """

        params.append(start_date)

    # End date filter
    if end_date:

        query += """
            AND collection_date <= ?
        """

        params.append(end_date)

    # Department filter
    if department:

        query += """
            AND department = ?
        """

        params.append(department)

    # Latest records first
    query += """
        ORDER BY id DESC
    """

    rows = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    # Create CSV in memory
    out = io.StringIO()

    writer = csv.writer(out)

    writer.writerow([
        "ID",
        "Employee Name",
        "Employee ID",
        "Department",
        "Printer Name",
        "Toner Type",
        "Quantity",
        "Collection Date",
        "Remarks",
        "Created At"
    ])

    for row in rows:

        writer.writerow(
            list(row)
        )

    data = io.BytesIO(
        out.getvalue().encode(
            "utf-8-sig"
        )
    )

    data.seek(0)

    # Create filename
    filename = "toner_collection"

    if start_date and end_date:

        filename += (
            f"_{start_date}_to_{end_date}"
        )

    elif start_date:

        filename += (
            f"_from_{start_date}"
        )

    elif end_date:

        filename += (
            f"_upto_{end_date}"
        )

    if department:

        filename += (
            f"_{department}"
        )

    filename += ".csv"

    return send_file(
        data,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename
    )


# -------------------------------------------------
# START APPLICATION
# -------------------------------------------------

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5000
    )