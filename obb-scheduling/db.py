"""SQLite schema + tiny data-access helpers for the OBB scheduling prototype."""
import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS shops (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  open_minutes INTEGER NOT NULL DEFAULT 480,
  close_minutes INTEGER NOT NULL DEFAULT 1440,
  weekly_budget REAL NOT NULL DEFAULT 0,
  address_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS employees (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'Staff',
  hourly_wage REAL NOT NULL DEFAULT 15.0,
  max_hours_week REAL NOT NULL DEFAULT 40
);
CREATE TABLE IF NOT EXISTS shifts (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  day INTEGER NOT NULL,              -- 0=Mon .. 6=Sun
  start_minutes INTEGER NOT NULL,
  end_minutes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS staffing_rules (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  min_staff INTEGER NOT NULL DEFAULT 2,
  days TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6',
  start_minutes INTEGER NOT NULL,
  end_minutes INTEGER NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS swap_requests (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  shift_id INTEGER NOT NULL REFERENCES shifts(id) ON DELETE CASCADE,
  from_employee_id INTEGER NOT NULL REFERENCES employees(id),
  to_employee_id INTEGER REFERENCES employees(id),
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  employee_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'staff'   -- 'manager' or 'staff'
);
CREATE TABLE IF NOT EXISTS availability (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  day INTEGER NOT NULL,              -- 0=Mon .. 6=Sun, weekly recurring
  start_minutes INTEGER NOT NULL,
  end_minutes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS time_off (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  week INTEGER NOT NULL DEFAULT 0,
  day INTEGER NOT NULL,              -- 0=Mon .. 6=Sun
  start_minutes INTEGER NOT NULL,
  end_minutes INTEGER NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',   -- pending/approved/denied
  created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                -- shift_assigned, swap_requested, ...
  text TEXT NOT NULL,
  link TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL,
  read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS schedule_commits (
  id INTEGER PRIMARY KEY,
  commit_hash TEXT NOT NULL,
  shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
  week INTEGER NOT NULL DEFAULT 0,
  author TEXT NOT NULL,
  action_kind TEXT NOT NULL,         -- shift_add, shift_delete, copy_week, clear_week, swap_approve, revert
  summary TEXT NOT NULL,
  before_json TEXT NOT NULL,         -- JSON list of shifts in (shop_id, week) BEFORE mutation
  after_json TEXT NOT NULL,          -- JSON list of shifts in (shop_id, week) AFTER mutation
  created TEXT NOT NULL,
  reverted INTEGER NOT NULL DEFAULT 0
);
"""


def _migrate(app):
    """Additive migrations for DBs created before v2.

    Safe under concurrent boot (multiple gunicorn workers import the app
    at once): the column guard is re-checked via try/except so a lost
    ALTER race is harmless instead of fatal.
    """
    db = sqlite3.connect(app.config["DB_PATH"], timeout=30)
    try:
        has = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shifts'"
        ).fetchone()
        cols = {r[1] for r in db.execute("PRAGMA table_info(shifts)").fetchall()} \
            if has else set()
        if "week" not in cols:
            try:
                db.execute("ALTER TABLE shifts ADD COLUMN week INTEGER NOT NULL DEFAULT 0")
                db.commit()
            except sqlite3.OperationalError as e:
                # Another worker added the column first — not an error.
                if "duplicate column" not in str(e):
                    raise
                db.rollback()
    finally:
        db.close()


def get_db():
    if "db" not in g:
        # timeout: wait on the SQLite write lock instead of failing fast —
        # gunicorn runs 2 workers sharing one DB file.
        g.db = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = sqlite3.connect(app.config["DB_PATH"])
        db.executescript(SCHEMA)
        db.commit()
        db.close()
    _migrate(app)


def q(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def q1(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid
