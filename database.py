# -*- coding: utf-8 -*-
"""
طبقة قاعدة البيانات (SQLite) | Database Layer
الجداول: users, sessions, runs, run_items, audit_log
ملاحظة: SQLite مكتفية ذاتياً للتشغيل الفوري. للإنتاج تُهاجَر إلى SQL Server
(نفس المخطط تقريباً) — استبدلي سلسلة الاتصال وأنواع الأعمدة فقط.
"""
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "taswiya.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
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
  ledger_name   TEXT,
  bank_name     TEXT,
  sheet         TEXT,
  matched       INTEGER, amount_diff INTEGER,
  ledger_only   INTEGER, bank_only   INTEGER, duplicates INTEGER,
  matched_total REAL,
  status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK(status IN ('draft','approved')),
  approved_by   INTEGER REFERENCES users(id),
  approved_at   TEXT
);

CREATE TABLE IF NOT EXISTS run_items (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id    INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  category  TEXT NOT NULL,            -- matched|amount_diff|ledger_only|bank_only|duplicates
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


def init_db(seed=True):
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()

    voucher_cols = {row[1] for row in conn.execute("PRAGMA table_info(vouchers)").fetchall()}
    if "source_unit" not in voucher_cols:
      conn.execute("ALTER TABLE vouchers ADD COLUMN source_unit TEXT")
    if "ocr_text" not in voucher_cols:
      conn.execute("ALTER TABLE vouchers ADD COLUMN ocr_text TEXT")
    if "ocr_source" not in voucher_cols:
      conn.execute("ALTER TABLE vouchers ADD COLUMN ocr_source TEXT")
    conn.commit()

    user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "password_changed_at" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_changed_at TEXT")
        conn.execute("UPDATE users SET password_changed_at = created_at")
    if "password_expires_days" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_expires_days INTEGER DEFAULT 0")
    conn.commit()

    if seed:
        cur = conn.execute("SELECT COUNT(*) c FROM users")
        if cur.fetchone()["c"] == 0:
            from auth import hash_password
            now = datetime.utcnow().isoformat()
            defaults = [
                ("admin", "admin123", "admin", "مدير النظام"),
                ("supervisor", "super123", "supervisor", "مشرف التسوية"),
                ("entry", "entry123", "entry", "موظف الإدخال"),
            ]
            for u, p, r, fn in defaults:
                h, s = hash_password(p)
                conn.execute(
                    "INSERT INTO users(username,password_hash,salt,role,full_name,created_at)"
                    " VALUES(?,?,?,?,?,?)", (u, h, s, r, fn, now))
            conn.commit()
    conn.close()


def log_action(user_id, username, action, detail=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO audit_log(user_id,username,action,detail,created_at) VALUES(?,?,?,?,?)",
        (user_id, username, action, detail, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
