"""Small helper around PyMySQL: one connection per request."""
from pathlib import Path

import pymysql
import pymysql.cursors
from flask import g

import config


def _iter_sql_statements(script):
    """Split a MySQL script while respecting DELIMITER changes."""
    delimiter = ";"
    pending = ""
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1]
            continue
        pending += line + "\n"
        while delimiter in pending:
            statement, pending = pending.split(delimiter, 1)
            if statement.strip():
                yield statement.strip()
    if pending.strip():
        yield pending.strip()


def initialize_database():
    """Create the configured database and load its schema and sample data once."""
    database = config.MYSQL_DB.replace("`", "``")
    connection = pymysql.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{database}`")
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE'",
                (config.MYSQL_DB,),
            )
            tables = {row[0] for row in cursor.fetchall()}

            expected_tables = {
                "admins", "tariff_slabs", "fixed_charges", "consumers",
                "meter_readings", "bills", "payments",
            }
            if not tables:
                root = Path(__file__).resolve().parent
                for filename in ("schema.sql", "seed.sql"):
                    script = (root / filename).read_text(encoding="utf-8")
                    for statement in _iter_sql_statements(script):
                        cursor.execute(statement)
                print(f"Initialized database '{config.MYSQL_DB}' with sample data.")
            elif not expected_tables.issubset(tables):
                missing = ", ".join(sorted(expected_tables - tables))
                raise RuntimeError(
                    f"Database '{config.MYSQL_DB}' is only partially initialized "
                    f"(missing tables: {missing})."
                )
    finally:
        connection.close()


def get_db():
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,  # rows come back as dicts
            autocommit=False,
        )
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_all(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    """Run one INSERT/UPDATE/DELETE and commit. Returns the new row id."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            new_id = cur.lastrowid
        db.commit()
        return new_id
    except Exception:
        db.rollback()
        raise
