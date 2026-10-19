"""SQLite schema + tiny data-access helpers for the OBB grants prototype."""
import sqlite3
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT '',
  contact_note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  funder TEXT NOT NULL DEFAULT '',
  deadline TEXT NOT NULL DEFAULT '',        -- ISO date YYYY-MM-DD, '' = none
  amount REAL NOT NULL DEFAULT 0,            -- '' means unspecified
  eligibility_notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'researching', -- researching/drafting/submitted/won/lost
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS boilerplates (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  block_name TEXT NOT NULL,                  -- e.g. Mission, History, Budget summary, Contact
  body TEXT NOT NULL DEFAULT '',
  updated TEXT NOT NULL DEFAULT ''           -- ISO date of last edit
);
CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'drafting',   -- drafting/ready/submitted
  created TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS app_sections (
  id INTEGER PRIMARY KEY,
  application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  position INTEGER NOT NULL DEFAULT 0,
  heading TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  word_target INTEGER NOT NULL DEFAULT 0,    -- 0 = no target
  body TEXT NOT NULL DEFAULT '',
  contributor TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
  opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
  title TEXT NOT NULL DEFAULT '',
  funder TEXT NOT NULL DEFAULT '',
  submitted_at TEXT NOT NULL DEFAULT '',     -- ISO date
  outcome TEXT NOT NULL DEFAULT 'pending',   -- pending/won/lost
  award_amount REAL NOT NULL DEFAULT 0,
  notes TEXT NOT NULL DEFAULT ''
);
-- v2: named per-funder section templates, saved and reused
CREATE TABLE IF NOT EXISTS app_templates (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,                        -- e.g. "Manitoba Trades Fund template"
  funder TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS app_template_sections (
  id INTEGER PRIMARY KEY,
  template_id INTEGER NOT NULL REFERENCES app_templates(id) ON DELETE CASCADE,
  position INTEGER NOT NULL DEFAULT 0,
  heading TEXT NOT NULL,
  prompt TEXT NOT NULL DEFAULT '',
  word_target INTEGER NOT NULL DEFAULT 0
);
-- v2: in-app deadline reminders (email/SMS seam lives in app.py)
CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                        -- due_soon_30 / due_soon_7 / due_soon_1 / overdue
  message TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL DEFAULT '',          -- ISO date generated
  read INTEGER NOT NULL DEFAULT 0            -- 0 = unread, 1 = read
);
-- v3: git-backed grant section revision log & 1-click undo
CREATE TABLE IF NOT EXISTS grant_commits (
  id INTEGER PRIMARY KEY,
  commit_hash TEXT NOT NULL,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  section_id INTEGER NOT NULL,
  section_heading TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  action_kind TEXT NOT NULL DEFAULT 'section_edit',
  summary TEXT NOT NULL DEFAULT '',
  before_body TEXT NOT NULL DEFAULT '',
  after_body TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL DEFAULT '',
  reverted INTEGER NOT NULL DEFAULT 0
);
"""


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


def q(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def q1(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid
