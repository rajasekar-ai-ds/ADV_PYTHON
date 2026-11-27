"""Electricity Bill Management System - Flask + MySQL."""
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

import pymysql
from flask import (Flask, flash, redirect, render_template, request,
                    session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
from billing import energy_charge
from db import close_db, execute, get_db, initialize_database, query_all, query_one

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(close_db)

CONNECTION_TYPES = ["DOMESTIC", "COMMERCIAL"]
PAYMENT_METHODS = ["CASH", "UPI", "CARD", "NET_BANKING"]


# ---------------------------------------------------------------- auth
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "admin" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def ensure_default_admin():
    """First run: create admin / admin123 if there is no admin yet."""
    if query_one("SELECT COUNT(*) AS n FROM admins")["n"] == 0:
        execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)",
                ("admin", generate_password_hash("admin123")))


@app.route("/login", methods=["GET", "POST"])
def login():
    ensure_default_admin()
    if request.method == "POST":
        user = query_one("SELECT * FROM admins WHERE username = %s",
                        (request.form["username"].strip(),))
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session["admin"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- dashboard
@app.route("/")
@login_required
def dashboard():
    stats = query_one("""
        SELECT
          (SELECT COUNT(*) FROM consumers) AS consumers,
          (SELECT COUNT(*) FROM bills WHERE status = 'UNPAID') AS unpaid_bills,
          (SELECT COALESCE(SUM(total_amount), 0) FROM bills WHERE status = 'UNPAID') AS pending_amount,
          (SELECT COALESCE(SUM(amount_paid), 0) FROM payments
             WHERE YEAR(payment_date) = YEAR(CURDATE())
               AND MONTH(payment_date) = MONTH(CURDATE())) AS collected_this_month,
          (SELECT COUNT(*) FROM v_bill_details WHERE is_overdue = 1) AS overdue_bills
    """)
    recent = query_all("SELECT * FROM v_bill_details ORDER BY bill_id DESC LIMIT 5")
    return render_template("dashboard.html", stats=stats, recent=recent)


# ---------------------------------------------------------------- consumers
@app.route("/consumers")
@login_required
def consumers():
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        rows = query_all("""SELECT * FROM consumers
                            WHERE name LIKE %s OR service_no LIKE %s OR phone LIKE %s
                            ORDER BY consumer_id""", (like, like, like))
    else:
        rows = query_all("SELECT * FROM consumers ORDER BY consumer_id")
    return render_template("consumers.html", consumers=rows, q=q)


def read_consumer_form():
    f = request.form
    data = {
        "service_no": f.get("service_no", "").strip(),
        "name": f.get("name", "").strip(),
        "address": f.get("address", "").strip(),
        "phone": f.get("phone", "").strip(),
        "email": f.get("email", "").strip() or None,
        "connection_type": f.get("connection_type", "DOMESTIC"),
        "initial_reading": f.get("initial_reading", "0").strip() or "0",
    }
    errors = []
    for field in ("service_no", "name", "address", "phone"):
        if not data[field]:
            errors.append(f"{field.replace('_', ' ').title()} is required")
    if data["phone"] and (not data["phone"].isdigit() or len(data["phone"]) != 10):
        errors.append("Phone must be 10 digits")
    if data["connection_type"] not in CONNECTION_TYPES:
        errors.append("Invalid connection type")
    if not data["initial_reading"].isdigit():
        errors.append("Initial reading must be a non-negative whole number")
    return data, errors


@app.route("/consumers/new", methods=["GET", "POST"])
@login_required
def consumer_new():
    if request.method == "POST":
        data, errors = read_consumer_form()
        if not errors:
            try:
                cid = execute("""INSERT INTO consumers
                    (service_no, name, address, phone, email, connection_type, initial_reading)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (data["service_no"], data["name"], data["address"], data["phone"],
                     data["email"], data["connection_type"], int(data["initial_reading"])))
                flash("Consumer added", "success")
                return redirect(url_for("consumer_detail", consumer_id=cid))
            except pymysql.err.IntegrityError:
                errors.append("Service number already exists")
        for e in errors:
            flash(e, "error")
        return render_template("consumer_form.html", c=data, types=CONNECTION_TYPES, editing=False)
    return render_template("consumer_form.html", c={}, types=CONNECTION_TYPES, editing=False)


@app.route("/consumers/<int:consumer_id>/edit", methods=["GET", "POST"])
@login_required
def consumer_edit(consumer_id):
    c = query_one("SELECT * FROM consumers WHERE consumer_id = %s", (consumer_id,))
    if not c:
        flash("Consumer not found", "error")
        return redirect(url_for("consumers"))
    has_readings = query_one("SELECT COUNT(*) AS n FROM meter_readings WHERE consumer_id = %s",
                             (consumer_id,))["n"] > 0
    if request.method == "POST":
        data, errors = read_consumer_form()
        if has_readings:
            data["initial_reading"] = str(c["initial_reading"])  # locked once billing starts
        if not errors:
            try:
                execute("""UPDATE consumers SET service_no=%s, name=%s, address=%s, phone=%s,
                           email=%s, connection_type=%s, initial_reading=%s
                           WHERE consumer_id=%s""",
                        (data["service_no"], data["name"], data["address"], data["phone"],
                         data["email"], data["connection_type"], int(data["initial_reading"]),
                         consumer_id))
                flash("Consumer updated", "success")
                return redirect(url_for("consumer_detail", consumer_id=consumer_id))
            except pymysql.err.IntegrityError:
                errors.append("Service number already exists")
        for e in errors:
            flash(e, "error")
        data["consumer_id"] = consumer_id
        return render_template("consumer_form.html", c=data, types=CONNECTION_TYPES,
                               editing=True, lock_initial=has_readings)
    return render_template("consumer_form.html", c=c, types=CONNECTION_TYPES,
                           editing=True, lock_initial=has_readings)


@app.route("/consumers/<int:consumer_id>/delete", methods=["POST"])
@login_required
def consumer_delete(consumer_id):
    execute("DELETE FROM consumers WHERE consumer_id = %s", (consumer_id,))
    flash("Consumer and their readings, bills and payments deleted", "success")
    return redirect(url_for("consumers"))


@app.route("/consumers/<int:consumer_id>")
@login_required
def consumer_detail(consumer_id):
    c = query_one("SELECT * FROM consumers WHERE consumer_id = %s", (consumer_id,))
    if not c:
        flash("Consumer not found", "error")
        return redirect(url_for("consumers"))
    bills = query_all("SELECT * FROM v_bill_details WHERE consumer_id = %s ORDER BY bill_id DESC",
                      (consumer_id,))
    return render_template("consumer_detail.html", c=c, bills=bills,
                           last_reading=last_reading(consumer_id), today=date.today())


# ---------------------------------------------------------------- readings + bill generation
def last_reading(consumer_id):
    """Latest meter value: the newest reading, or the initial reading if none."""
    row = query_one("""SELECT reading_value FROM meter_readings WHERE consumer_id = %s
                       ORDER BY reading_date DESC, reading_id DESC LIMIT 1""", (consumer_id,))
    if row:
        return row["reading_value"]
    return query_one("SELECT initial_reading FROM consumers WHERE consumer_id = %s",
                     (consumer_id,))["initial_reading"]


@app.route("/consumers/<int:consumer_id>/reading", methods=["POST"])
@login_required
def add_reading(consumer_id):
    """Record a meter reading and generate its bill in ONE transaction."""
    c = query_one("SELECT * FROM consumers WHERE consumer_id = %s", (consumer_id,))
    if not c:
        flash("Consumer not found", "error")
        return redirect(url_for("consumers"))

    value = request.form.get("reading_value", "").strip()
    reading_date = request.form.get("reading_date") or date.today().isoformat()
    previous = last_reading(consumer_id)
    if not value.isdigit():
        flash("Reading must be a whole number", "error")
        return redirect(url_for("consumer_detail", consumer_id=consumer_id))
    current = int(value)
    if current < previous:
        flash(f"Current reading ({current}) cannot be less than previous reading ({previous})", "error")
        return redirect(url_for("consumer_detail", consumer_id=consumer_id))

    units = current - previous
    slabs = query_all("""SELECT from_unit, to_unit, rate_per_unit FROM tariff_slabs
                         WHERE connection_type = %s ORDER BY from_unit""", (c["connection_type"],))
    fixed_row = query_one("SELECT amount FROM fixed_charges WHERE connection_type = %s",
                          (c["connection_type"],))
    fixed = Decimal(str(fixed_row["amount"])) if fixed_row else Decimal("0")
    energy, _ = energy_charge(units, slabs)
    total = energy + fixed
    bill_date = date.fromisoformat(reading_date)
    due_date = bill_date + timedelta(days=config.BILL_DUE_DAYS)

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""INSERT INTO meter_readings (consumer_id, reading_date, reading_value)
                           VALUES (%s, %s, %s)""", (consumer_id, reading_date, current))
            reading_id = cur.lastrowid
            cur.execute("""INSERT INTO bills (consumer_id, reading_id, previous_reading, current_reading,
                             units_consumed, energy_charge, fixed_charge, total_amount, bill_date, due_date)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (consumer_id, reading_id, previous, current, units, energy, fixed, total,
                         bill_date, due_date))
            bill_id = cur.lastrowid
        db.commit()
    except Exception:
        db.rollback()  # neither the reading nor the bill is saved
        flash("Could not generate the bill", "error")
        return redirect(url_for("consumer_detail", consumer_id=consumer_id))

    flash(f"Bill generated: {units} units, Rs. {total}", "success")
    return redirect(url_for("bill_view", bill_id=bill_id))


# ---------------------------------------------------------------- bills + payments
@app.route("/bills")
@login_required
def bills():
    status = request.args.get("status", "")
    if status in ("UNPAID", "PAID"):
        rows = query_all("SELECT * FROM v_bill_details WHERE status = %s ORDER BY bill_id DESC", (status,))
    elif status == "OVERDUE":
        rows = query_all("SELECT * FROM v_bill_details WHERE is_overdue = 1 ORDER BY bill_id DESC")
    else:
        rows = query_all("SELECT * FROM v_bill_details ORDER BY bill_id DESC")
    return render_template("bills.html", bills=rows, status=status)


@app.route("/bills/<int:bill_id>")
@login_required
def bill_view(bill_id):
    b = query_one("""SELECT b.*, c.service_no, c.name, c.address, c.phone, c.connection_type
                     FROM bills b JOIN consumers c ON c.consumer_id = b.consumer_id
                     WHERE b.bill_id = %s""", (bill_id,))
    if not b:
        flash("Bill not found", "error")
        return redirect(url_for("bills"))
    slabs = query_all("""SELECT from_unit, to_unit, rate_per_unit FROM tariff_slabs
                         WHERE connection_type = %s ORDER BY from_unit""", (b["connection_type"],))
    recomputed, breakdown = energy_charge(b["units_consumed"], slabs)
    if recomputed != b["energy_charge"]:
        breakdown = None  # tariff changed after this bill; the stored amount is what counts
    payment = query_one("SELECT * FROM payments WHERE bill_id = %s", (bill_id,))
    return render_template("bill_view.html", b=b, breakdown=breakdown, payment=payment,
                           methods=PAYMENT_METHODS, today=date.today())


@app.route("/bills/<int:bill_id>/pay", methods=["POST"])
@login_required
def pay_bill(bill_id):
    b = query_one("SELECT * FROM bills WHERE bill_id = %s", (bill_id,))
    if not b:
        flash("Bill not found", "error")
        return redirect(url_for("bills"))
    if b["status"] == "PAID":
        flash("This bill is already paid", "error")
        return redirect(url_for("bill_view", bill_id=bill_id))
    method = request.form.get("method")
    if method not in PAYMENT_METHODS:
        flash("Choose a payment method", "error")
        return redirect(url_for("bill_view", bill_id=bill_id))
    try:
        # The trigger trg_payment_marks_bill_paid sets bills.status = 'PAID'
        execute("""INSERT INTO payments (bill_id, amount_paid, payment_date, method)
                   VALUES (%s, %s, %s, %s)""", (bill_id, b["total_amount"], date.today(), method))
        flash("Payment recorded", "success")
    except pymysql.err.IntegrityError:
        flash("This bill is already paid", "error")
    return redirect(url_for("bill_view", bill_id=bill_id))


@app.route("/payments")
@login_required
def payments():
    rows = query_all("""SELECT p.*, c.service_no, c.name FROM payments p
                        JOIN bills b ON b.bill_id = p.bill_id
                        JOIN consumers c ON c.consumer_id = b.consumer_id
                        ORDER BY p.payment_id DESC""")
    return render_template("payments.html", payments=rows)


# ---------------------------------------------------------------- tariff
@app.route("/tariff", methods=["GET", "POST"])
@login_required
def tariff():
    if request.method == "POST":
        try:
            for key, val in request.form.items():
                if key.startswith("rate_"):
                    execute("UPDATE tariff_slabs SET rate_per_unit = %s WHERE slab_id = %s",
                            (Decimal(val), int(key[5:])))
                elif key.startswith("fixed_"):
                    execute("UPDATE fixed_charges SET amount = %s WHERE connection_type = %s",
                            (Decimal(val), key[6:]))
            flash("Tariff updated. New rates apply to bills generated from now on.", "success")
        except Exception:
            flash("Rates must be non-negative numbers", "error")
        return redirect(url_for("tariff"))
    slabs = query_all("SELECT * FROM tariff_slabs ORDER BY connection_type, from_unit")
    fixed = query_all("SELECT * FROM fixed_charges ORDER BY connection_type")
    return render_template("tariff.html", slabs=slabs, fixed=fixed)


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
