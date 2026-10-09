from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import sqlite3
import csv
import io
from datetime import datetime
import os
from functools import wraps
from flask import session
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("Please configure the SECRET_KEY environment variable.")

DB = "toner.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = db()
        user = conn.execute(
            """
            SELECT id, username, password_hash, role
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("home"))

        flash("Invalid username or password.")

    return render_template("login.html")


# Logout
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# Require login
def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


# Require Admin role
def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "Admin":
            flash("You do not have permission to perform this action.")
            return redirect(url_for("home"))

        return view(*args, **kwargs)
    return wrapped_view



# =========================================================
# TONER MASTER - 22 ITEMS
# =========================================================

TONER_MASTER = [
    ("4601020141", "TONER FOR HP LJ M427DW 28A (C5F97A)"),
    ("4601020142", "TONER FOR HP LJ M706N 93A (CZ192A)"),
    ("4601020156", "CANON 337 TONER"),
    ("4603060224", "HP 335X TONER"),
    ("4601022901", "LASERJET TONER CARTRIDGE FOR HP LASERJET 12 A"),
    ("4601020009", "HP LASERJET CARTRIDGE CC388A FOR HP LASE"),
    ("4601020112", "CANON 045 TONER CARTRIDGE FOR LBP612C (M"),
    ("4601020113", "CANON 045 TONER CARTRIDGE FOR LBP612C(YE"),
    ("4601020114", "CANON 045 TONER CARTRIDGE FOR LBP612C(BL"),
    ("4601020115", "CANON 045 TONER CARTRIDGE FOR LBP612C(CY"),
    ("4603020057", "HP 119A BLACK CARTRIDGE FOR 150NW HP PRI"),
    ("4603020058", "HP 119A CYAN CARTRIDGE FOR 150NW HP PRIN"),
    ("4603020059", "HP 119A YELLOW CARTRIDGE FOR 150NW HP PR"),
    ("4603020060", "HP 119A MAGENTA CARTRIDGE FOR 150NW HP P"),
    ("4601020370", "HP 222A BLACK CARTRIDGE FOR HP MFP 3303"),
    ("4601020371", "HP 222A CYAN CARTRIDGE FOR HP MFP 3303 P"),
    ("4601020372", "HP 222A YELLOW CARTRIDGE FOR HP MFP 3303"),
    ("4601020373", "HP 222A MAGENTA CARTRIDGE FOR HP MFP 3303"),
    ("RENTAL0001", "HP 92A TONER FOR HP 706 PRINTER"),
    ("RENTAL0002", "HP W1520X TONER FOR HP 427 PRINTER"),
    ("RENTAL0003", "HP TONNER 277A TONER FOR HP 4004 PRINTER"),
    ("RENTAL0004", "HP TONNER 335X TONER FOR HP 440 PRINTER"),
]


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():

    conn = db()

    
    # Create users table for login
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Admin', 'User'))
        )
    """)


    # -----------------------------------------------------
    # Employee Master
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_master (
            employee_code TEXT PRIMARY KEY,
            employee_name TEXT NOT NULL,
            designation TEXT,
            department TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # Toner Collection
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS toner_collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_name TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            department TEXT NOT NULL,
            printer_name TEXT,
            toner_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            collection_date TEXT NOT NULL,
            remarks TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # Toner Stock
    #
    # This matches your EXISTING database.
    # -----------------------------------------------------

    conn.execute("""
        CREATE TABLE IF NOT EXISTS toner_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            toner_type TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            item_code TEXT,
            toner_name TEXT
        )
    """)

    # -----------------------------------------------------
    # Add missing toner master items
    # -----------------------------------------------------

    for item_code, toner_name in TONER_MASTER:

        existing = conn.execute("""
            SELECT id
            FROM toner_stock
            WHERE item_code = ?
        """, (item_code,)).fetchone()

        if existing is None:

            conn.execute("""
                INSERT INTO toner_stock
                (
                    toner_type,
                    quantity,
                    updated_at,
                    item_code,
                    toner_name
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                toner_name,
                0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                item_code,
                toner_name
            ))

    conn.commit()
    conn.close()


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
@login_required
def home():

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = db()

    # -----------------------------------------------------
    # Collection Records
    # -----------------------------------------------------

    if search:

        rows = conn.execute("""
            SELECT *
            FROM toner_collection
            WHERE employee_name LIKE ?
               OR employee_id LIKE ?
               OR department LIKE ?
               OR toner_type LIKE ?
               OR remarks LIKE ?
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

    # -----------------------------------------------------
    # Statistics
    # -----------------------------------------------------

    total = conn.execute("""
        SELECT COUNT(*) AS c
        FROM toner_collection
    """).fetchone()["c"]

    people = conn.execute("""
        SELECT COUNT(DISTINCT employee_id) AS c
        FROM toner_collection
    """).fetchone()["c"]

    # -----------------------------------------------------
    # Departments
    # -----------------------------------------------------

    departments = conn.execute("""
        SELECT DISTINCT department
        FROM employee_master
        WHERE department IS NOT NULL
        AND department != ''
        ORDER BY department
    """).fetchall()

    # -----------------------------------------------------
    # Live Toner Stock
    # -----------------------------------------------------

    stock = conn.execute("""
        SELECT
            id,
            item_code,
            toner_name,
            toner_type,
            quantity,
            updated_at
        FROM toner_stock
        ORDER BY id
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        rows=rows,
        total=total,
        people=people,
        search=search,
        departments=departments,
        stock=stock,
        toner_master=TONER_MASTER
    )


# =========================================================
# EMPLOYEE AUTO FETCH
# =========================================================

@app.get("/employee/<employee_code>")
@login_required
def get_employee(employee_code):

    conn = db()

    employee = conn.execute("""
        SELECT
            employee_code,
            employee_name,
            designation,
            department
        FROM employee_master
        WHERE employee_code = ?
    """, (
        employee_code.strip(),
    )).fetchone()

    conn.close()

    if employee:

        return jsonify({
            "found": True,
            "employee_code": employee["employee_code"],
            "employee_name": employee["employee_name"],
            "designation": employee["designation"],
            "department": employee["department"]
        })

    return jsonify({
        "found": False
    })


# =========================================================
# SAVE TONER COLLECTION
# =========================================================

@app.post("/submit")
@login_required
def submit():

    employee_id = request.form.get(
        "employee_id",
        ""
    ).strip()

    item_code = request.form.get(
        "item_code",
        ""
    ).strip()

    quantity_text = request.form.get(
        "quantity",
        ""
    ).strip()

    collection_date = request.form.get(
        "collection_date",
        ""
    ).strip()

    remarks = request.form.get(
        "remarks",
        ""
    ).strip()

    # -----------------------------------------------------
    # Required fields
    # -----------------------------------------------------

    if not employee_id or not item_code or not quantity_text or not collection_date:

        flash(
            "Please fill all required fields.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Validate quantity
    # -----------------------------------------------------

    try:

        quantity = int(quantity_text)

        if quantity < 1:
            raise ValueError

    except ValueError:

        flash(
            "Quantity must be a positive number.",
            "error"
        )

        return redirect(url_for("home"))

    conn = db()

    # -----------------------------------------------------
    # Employee
    # -----------------------------------------------------

    employee = conn.execute("""
        SELECT
            employee_name,
            department
        FROM employee_master
        WHERE employee_code = ?
    """, (
        employee_id,
    )).fetchone()

    if not employee:

        conn.close()

        flash(
            "Employee code not found.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Toner
    # -----------------------------------------------------

    toner = conn.execute("""
        SELECT
            item_code,
            toner_name,
            quantity
        FROM toner_stock
        WHERE item_code = ?
    """, (
        item_code,
    )).fetchone()

    if not toner:

        conn.close()

        flash(
            "Toner item not found.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Check Stock
    # -----------------------------------------------------

    current_stock = toner["quantity"]

    if quantity > current_stock:

        conn.close()

        flash(
            f"Insufficient stock. Available stock for "
            f"{toner['toner_name']} is {current_stock}.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Calculate New Stock
    # -----------------------------------------------------

    new_stock = current_stock - quantity

    # -----------------------------------------------------
    # Save Collection Record
    # -----------------------------------------------------

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
    "",
    toner["toner_name"],
    quantity,
    collection_date,
    remarks,
    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
))

    # -----------------------------------------------------
    # Automatically Deduct Stock
    # -----------------------------------------------------

    conn.execute("""
        UPDATE toner_stock
        SET
            quantity = ?,
            updated_at = ?,
            toner_name = ?,
            toner_type = ?
        WHERE item_code = ?
    """, (
        new_stock,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        toner["toner_name"],
        toner["toner_name"],
        item_code
    ))

    conn.commit()
    conn.close()

    flash(
        f"Record saved successfully. "
        f"{toner['toner_name']} stock is now {new_stock}.",
        "success"
    )

    return redirect(url_for("home"))


# =========================================================
# MANUAL STOCK UPDATE
# =========================================================

@app.post("/update-stock")
@admin_required
def update_stock():

    item_code = request.form.get(
        "stock_item_code",
        ""
    ).strip()

    quantity_text = request.form.get(
        "stock_quantity",
        ""
    ).strip()

    if not item_code or not quantity_text:

        flash(
            "Please select toner and enter stock quantity.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Validate quantity
    # -----------------------------------------------------

    try:

        quantity = int(quantity_text)

        if quantity < 0:
            raise ValueError

    except ValueError:

        flash(
            "Stock quantity must be 0 or greater.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Find toner
    # -----------------------------------------------------

    toner_name = None

    for code, name in TONER_MASTER:

        if code == item_code:

            toner_name = name
            break

    if toner_name is None:

        flash(
            "Invalid toner item.",
            "error"
        )

        return redirect(url_for("home"))

    conn = db()

    # -----------------------------------------------------
    # Update Existing Stock
    # -----------------------------------------------------

    conn.execute("""
        UPDATE toner_stock
        SET
            quantity = ?,
            updated_at = ?,
            toner_name = ?,
            toner_type = ?
        WHERE item_code = ?
    """, (
        quantity,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        toner_name,
        toner_name,
        item_code
    ))

    conn.commit()
    conn.close()

    flash(
        f"Stock updated successfully. "
        f"{toner_name}: {quantity}",
        "success"
    )

    return redirect(url_for("home"))


# =========================================================
# ADD STOCK
# =========================================================

@app.post("/add-stock")
@admin_required
def add_stock():

    item_code = request.form.get(
        "stock_item_code",
        ""
    ).strip()

    quantity_text = request.form.get(
        "stock_quantity",
        ""
    ).strip()

    if not item_code or not quantity_text:

        flash(
            "Please select toner and enter quantity to add.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Validate quantity
    # -----------------------------------------------------

    try:

        add_quantity = int(quantity_text)

        if add_quantity < 1:
            raise ValueError

    except ValueError:

        flash(
            "Add quantity must be a positive number.",
            "error"
        )

        return redirect(url_for("home"))

    # -----------------------------------------------------
    # Find toner name
    # -----------------------------------------------------

    toner_name = None

    for code, name in TONER_MASTER:

        if code == item_code:

            toner_name = name
            break

    if toner_name is None:

        flash(
            "Invalid toner item.",
            "error"
        )

        return redirect(url_for("home"))

    conn = db()

    # -----------------------------------------------------
    # Get existing stock
    # -----------------------------------------------------

    toner = conn.execute("""
        SELECT quantity
        FROM toner_stock
        WHERE item_code = ?
    """, (
        item_code,
    )).fetchone()

    if not toner:

        conn.close()

        flash(
            "Toner stock record not found.",
            "error"
        )

        return redirect(url_for("home"))

    current_stock = toner["quantity"]

    # -----------------------------------------------------
    # ADD to existing stock
    # -----------------------------------------------------

    new_stock = current_stock + add_quantity

    conn.execute("""
        UPDATE toner_stock
        SET
            quantity = ?,
            updated_at = ?,
            toner_name = ?,
            toner_type = ?
        WHERE item_code = ?
    """, (
        new_stock,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        toner_name,
        toner_name,
        item_code
    ))

    conn.commit()
    conn.close()

    flash(
        f"Stock added successfully. "
        f"{toner_name}: {current_stock} + {add_quantity} = {new_stock}",
        "success"
    )

    return redirect(url_for("home"))

# =========================================================
# EXPORT CSV
# =========================================================

@app.get("/export")
@login_required
def export():

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

    query = """
        SELECT
            id,
            employee_name,
            employee_id,
            department,
            toner_type,
            quantity,
            collection_date,
            remarks,
            created_at
        FROM toner_collection
        WHERE 1=1
    """

    params = []

    if start_date:

        query += """
            AND collection_date >= ?
        """

        params.append(start_date)

    if end_date:

        query += """
            AND collection_date <= ?
        """

        params.append(end_date)

    if department:

        query += """
            AND department = ?
        """

        params.append(department)

    query += """
        ORDER BY id DESC
    """

    rows = conn.execute(
        query,
        params
    ).fetchall()

    conn.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Employee Name",
        "Employee ID",
        "Department",
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
        output.getvalue().encode(
            "utf-8-sig"
        )
    )

    data.seek(0)

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



# =========================================================
# START APPLICATION
# =========================================================

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
