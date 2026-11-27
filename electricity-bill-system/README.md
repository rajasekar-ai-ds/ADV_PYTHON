# Electricity Bill Management System (Flask + MySQL)

A web app for an electricity board office to manage consumers, record meter readings, generate slab-wise bills, and record payments.

## Features
- **Admin login** (password stored as a hash, session-based)
- **Consumers:** add, edit, delete, search by name / service number / phone
- **Meter reading → bill:** enter the current reading; the app computes units consumed and generates the bill in one database transaction
- **Slab-wise tariff:** different rates per unit range, separate for Domestic and Commercial; rates are editable from the Tariff page
- **Bills:** list with All / Unpaid / Overdue / Paid filters, printable bill with slab breakdown
- **Payments:** record a payment (Cash / UPI / Card / Net banking); a MySQL trigger marks the bill as PAID
- **Dashboard:** consumers, unpaid bills, pending amount, amount collected this month, overdue bills

## Tech stack
Python, Flask, Jinja2 templates, MySQL (PyMySQL driver), HTML/CSS.

## Database design
| Table | Purpose |
|---|---|
| `admins` | login users (hashed passwords) |
| `consumers` | consumer details, connection type, initial meter reading |
| `tariff_slabs` | rate per unit for each unit range and connection type |
| `fixed_charges` | fixed charge per bill for each connection type |
| `meter_readings` | every reading taken |
| `bills` | one bill per reading: units, energy charge, fixed charge, total, due date, status |
| `payments` | one payment per bill |

Also in `schema.sql`:
- **Trigger** `trg_payment_marks_bill_paid`: after a payment is inserted, sets the bill's status to `PAID`
- **View** `v_bill_details`: bills joined with consumers, plus an `is_overdue` flag
- **Constraints:** foreign keys with `ON DELETE CASCADE`, `UNIQUE` service number, `CHECK` constraints on readings and rates
- **Indexes** on readings (consumer, date) and bill status

## Bill calculation
`units = current reading − previous reading` (previous = last reading, or the initial reading for the first bill).

Each unit is charged at the rate of the slab it falls in. Example, Domestic, 250 units:

| Slab | Units | Rate | Amount |
|---|---|---|---|
| 1–100 | 100 | ₹0.00 | ₹0.00 |
| 101–200 | 100 | ₹2.35 | ₹235.00 |
| 201–400 | 50 | ₹4.70 | ₹235.00 |

Energy charge ₹470 + fixed charge ₹50 = **₹520.00**. Due date = bill date + 15 days. (Tariff values are sample values.)

## How to run
1. Install **Python 3.10+** and **MySQL Server 8**, then make sure the MySQL service is running.
2. Install the packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows   (Linux/WSL: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
3. Configure your MySQL connection in `config.py` or with environment variables. The MySQL user must be allowed to create the application database the first time:
   ```
   $env:MYSQL_PASSWORD="your_password"      # Windows PowerShell
   export MYSQL_PASSWORD="your_password"    # Linux/WSL
   ```
4. Run `python app.py`. On first launch, the app creates the configured database, tables, and sample data automatically; no MySQL command-line client is needed. Open http://127.0.0.1:5000.
5. Log in with **admin / admin123** (created automatically on first run).

## Project structure
```
app.py          Flask routes (login, consumers, readings, bills, payments, tariff)
billing.py      slab-wise bill calculation (pure function)
db.py           MySQL connection and query helpers
config.py       database settings
schema.sql      tables, trigger, view, indexes
seed.sql        sample tariff and consumers
templates/      Jinja2 HTML pages
static/         CSS
```
