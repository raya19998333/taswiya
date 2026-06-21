# -*- coding: utf-8 -*-
"""
Database layer — SQLite locally, PostgreSQL on Render (via DATABASE_URL env var).
"""
import os
import sqlite3
from pathlib import Path
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = Path(__file__).parent / "taswiya.db"


# ── Connection factory ────────────────────────────────────────────────────────

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    class _PgConn:
        """Thin wrapper making psycopg2 look like sqlite3 to the rest of the codebase."""
        def __init__(self, raw):
            self._raw = raw

        def execute(self, sql, params=None):
            sql = sql.replace("?", "%s")
            cur = self._raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur

        def commit(self): self._raw.commit()
        def close(self):  self._raw.close()

    def get_conn() -> "_PgConn":
        return _PgConn(psycopg2.connect(DATABASE_URL))

else:
    def get_conn():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


# ── Schemas ───────────────────────────────────────────────────────────────────

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  salt          TEXT NOT NULL,
  role          TEXT NOT NULL CHECK(role IN ('admin','supervisor','entry')),
  full_name     TEXT,
  created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token      TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  created_by    INTEGER NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL,
  ledger_name   TEXT, bank_name TEXT, sheet TEXT,
  matched       INTEGER, amount_diff INTEGER,
  ledger_only   INTEGER, bank_only   INTEGER, duplicates INTEGER,
  matched_total REAL,
  status        TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved')),
  approved_by   INTEGER REFERENCES users(id),
  approved_at   TEXT
);
CREATE TABLE IF NOT EXISTS run_items (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id    INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  category  TEXT NOT NULL,
  ref       TEXT,
  ledger_total REAL, bank_total REAL, diff REAL,
  description  TEXT, employee TEXT, txn_date TEXT, amount REAL
);
CREATE TABLE IF NOT EXISTS audit_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER REFERENCES users(id),
  username   TEXT,
  action     TEXT NOT NULL,
  detail     TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vouchers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  voucher_no    TEXT,
  voucher_date  TEXT NOT NULL,
  amount        REAL NOT NULL,
  currency      TEXT NOT NULL DEFAULT 'ر.ع',
  source_unit   TEXT,
  beneficiary   TEXT NOT NULL,
  description   TEXT,
  ocr_text      TEXT,
  ocr_source    TEXT,
  file_path     TEXT,
  file_name     TEXT,
  status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK(status IN ('draft','approved','cancelled')),
  created_by    INTEGER NOT NULL REFERENCES users(id),
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vouchers_no ON vouchers(voucher_no);
CREATE INDEX IF NOT EXISTS idx_vouchers_beneficiary ON vouchers(beneficiary);
CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(voucher_date);
"""

_PG_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, salt TEXT NOT NULL,
      role TEXT NOT NULL CHECK(role IN ('admin','supervisor','entry')),
      full_name TEXT, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS sessions (
      token TEXT PRIMARY KEY,
      user_id INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS runs (
      id SERIAL PRIMARY KEY,
      created_by INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL, ledger_name TEXT, bank_name TEXT, sheet TEXT,
      matched INTEGER, amount_diff INTEGER,
      ledger_only INTEGER, bank_only INTEGER, duplicates INTEGER,
      matched_total REAL,
      status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved')),
      approved_by INTEGER REFERENCES users(id), approved_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS run_items (
      id SERIAL PRIMARY KEY,
      run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
      category TEXT NOT NULL, ref TEXT,
      ledger_total REAL, bank_total REAL, diff REAL,
      description TEXT, employee TEXT, txn_date TEXT, amount REAL)""",
    """CREATE TABLE IF NOT EXISTS audit_log (
      id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
      username TEXT, action TEXT NOT NULL, detail TEXT,
      created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS vouchers (
      id SERIAL PRIMARY KEY, voucher_no TEXT,
      voucher_date TEXT NOT NULL, amount REAL NOT NULL,
      currency TEXT NOT NULL DEFAULT 'ر.ع',
      source_unit TEXT, beneficiary TEXT NOT NULL,
      description TEXT, ocr_text TEXT, ocr_source TEXT,
      file_path TEXT, file_name TEXT,
      status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','approved','cancelled')),
      created_by INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_vouchers_no ON vouchers(voucher_no)",
    "CREATE INDEX IF NOT EXISTS idx_vouchers_beneficiary ON vouchers(beneficiary)",
    "CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(voucher_date)",
]


# ── Shared helpers ────────────────────────────────────────────────────────────

def _seed(conn):
    from auth import hash_password
    now = datetime.utcnow().isoformat()
    for u, p, r, fn in [
        ("admin",      "admin123", "admin",      "مدير النظام"),
        ("supervisor", "super123", "supervisor", "مشرف التسوية"),
        ("entry",      "entry123", "entry",      "موظف الإدخال"),
    ]:
        h, s = hash_password(p)
        conn.execute(
            "INSERT INTO users(username,password_hash,salt,role,full_name,created_at)"
            " VALUES(?,?,?,?,?,?)", (u, h, s, r, fn, now))
    conn.commit()


# ── init_db ───────────────────────────────────────────────────────────────────

def init_db(seed=True):
    if DATABASE_URL:
        _init_pg(seed)
    else:
        _init_sqlite(seed)


def _init_sqlite(seed):
    conn = get_conn()
    conn.executescript(_SQLITE_SCHEMA)
    conn.commit()

    vcols = {row[1] for row in conn.execute("PRAGMA table_info(vouchers)").fetchall()}
    for col in ("source_unit", "ocr_text", "ocr_source"):
        if col not in vcols:
            conn.execute(f"ALTER TABLE vouchers ADD COLUMN {col} TEXT")
    conn.commit()

    ucols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "password_changed_at" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")
        conn.execute("UPDATE users SET password_changed_at = created_at")
    if "password_expires_days" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN password_expires_days INTEGER DEFAULT 0")
    conn.commit()

    if seed:
        if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
            _seed(conn)
    conn.close()


def _init_pg(seed):
    conn = get_conn()
    for stmt in _PG_SCHEMA:
        conn.execute(stmt)
    conn.commit()

    def pg_cols(table):
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        ).fetchall()
        return {r["column_name"] for r in rows}

    vcols = pg_cols("vouchers")
    for col in ("source_unit", "ocr_text", "ocr_source"):
        if col not in vcols:
            conn.execute(f"ALTER TABLE vouchers ADD COLUMN {col} TEXT")
    conn.commit()

    ucols = pg_cols("users")
    if "password_changed_at" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")
        conn.execute("UPDATE users SET password_changed_at = created_at")
    if "password_expires_days" not in ucols:
        conn.execute("ALTER TABLE users ADD COLUMN password_expires_days INTEGER DEFAULT 0")
    conn.commit()

    if seed:
        if conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] == 0:
            _seed(conn)
    conn.close()


# ── log_action ────────────────────────────────────────────────────────────────

def log_action(user_id, username, action, detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log(user_id,username,action,detail,created_at) VALUES(?,?,?,?,?)",
        (user_id, username, action, detail, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
