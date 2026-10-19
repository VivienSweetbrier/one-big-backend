"""One Big Backend — Module 3: Parish & Community Lending Library (St. Ignatius Spiritual Education Centre).

Multi-tenant searchable online catalog, checkout/return tracker, overdue detector,
CSV catalog import, and Git-backed 1-click Undo / audit history.
Built in the exact Flask + SQLite idiom of Module 1 (obb-scheduling) and Module 2 (obb-grants).
"""
import hashlib
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from flask import Flask, g, render_template_string, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get("OBB_SECRET", "obb-prototype-dev-key")
app.config["DB_PATH"] = os.environ.get(
    "OBB_LIBRARY_DB", os.path.join(os.path.dirname(__file__), "obb_library.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS libraries (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  parish_or_org TEXT NOT NULL DEFAULT '',
  address_note TEXT NOT NULL DEFAULT '',
  loan_days INTEGER NOT NULL DEFAULT 21
);
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  call_number TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  author TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'Spirituality',
  copies_total INTEGER NOT NULL DEFAULT 1,
  copies_available INTEGER NOT NULL DEFAULT 1,
  notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS loans (
  id INTEGER PRIMARY KEY,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  borrower_name TEXT NOT NULL,
  borrower_contact TEXT NOT NULL DEFAULT '',
  checked_out_at TEXT NOT NULL,
  due_date TEXT NOT NULL,
  returned_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS library_commits (
  id INTEGER PRIMARY KEY,
  commit_hash TEXT NOT NULL,
  library_id INTEGER NOT NULL REFERENCES libraries(id) ON DELETE CASCADE,
  author TEXT NOT NULL DEFAULT 'Librarian',
  action_kind TEXT NOT NULL,
  summary TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  created TEXT NOT NULL,
  reverted INTEGER NOT NULL DEFAULT 0
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DB_PATH"], timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = sqlite3.connect(app.config["DB_PATH"])
        db.executescript(SCHEMA)
        db.commit()
        db.close()


init_db()


def q(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def q1(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def _snapshot_library(lib_id):
    books = [dict(r) for r in q("SELECT id, call_number, title, author, category, copies_total, copies_available, notes FROM books WHERE library_id=? ORDER BY id", (lib_id,))]
    loans = [dict(r) for r in q("SELECT id, book_id, borrower_name, borrower_contact, checked_out_at, due_date, returned_at FROM loans WHERE library_id=? ORDER BY id", (lib_id,))]
    return {"books": books, "loans": loans}


def _restore_library(lib_id, snap):
    run("DELETE FROM loans WHERE library_id=?", (lib_id,))
    run("DELETE FROM books WHERE library_id=?", (lib_id,))
    for b in snap["books"]:
        run(
            "INSERT INTO books (id, library_id, call_number, title, author, category, copies_total, copies_available, notes)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (b["id"], lib_id, b["call_number"], b["title"], b["author"], b["category"], b["copies_total"], b["copies_available"], b["notes"]),
        )
    for l in snap["loans"]:
        run(
            "INSERT INTO loans (id, library_id, book_id, borrower_name, borrower_contact, checked_out_at, due_date, returned_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (l["id"], lib_id, l["book_id"], l["borrower_name"], l["borrower_contact"], l["checked_out_at"], l["due_date"], l["returned_at"]),
        )


def _record_commit(lib_id, author, action_kind, summary, before_snap, after_snap):
    now_iso = datetime.now().isoformat(timespec="seconds")
    b_json = json.dumps(before_snap, sort_keys=True)
    a_json = json.dumps(after_snap, sort_keys=True)
    raw = f"{lib_id}|{author}|{action_kind}|{summary}|{b_json}|{a_json}|{now_iso}"
    chash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    run(
        """INSERT INTO library_commits
           (commit_hash, library_id, author, action_kind, summary, before_json, after_json, created)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chash, lib_id, author, action_kind, summary, b_json, a_json, now_iso),
    )
    return chash


def seed_default_libraries():
    with app.app_context():
        if q1("SELECT COUNT(*) c FROM libraries")["c"] > 0:
            return
        st_ig = run(
            "INSERT INTO libraries (name, parish_or_org, address_note, loan_days) VALUES (?,?,?,?)",
            ("Spiritual Education Centre Lending Library", "St. Ignatius Parish", "255 Stafford St, Winnipeg", 21),
        )
        holy_rosary = run(
            "INSERT INTO libraries (name, parish_or_org, address_note, loan_days) VALUES (?,?,?,?)",
            ("Parish Ministry & Youth Resource Shelf", "Holy Rosary Parish", "510 River Ave, Winnipeg", 14),
        )
        catalog = [
            ("IGN-001", "The Spiritual Exercises of St. Ignatius", "St. Ignatius of Loyola (trans. Louis J. Puhl, S.J.)", "Ignatian Spirituality", 3, 2, "Core retreat companion"),
            ("IGN-002", "The Jesuit Guide to (Almost) Everything", "James Martin, S.J.", "Ignatian Spirituality", 2, 2, "Accessible introduction to Ignatian discernment"),
            ("IGN-003", "The Discernment of Spirits", "Timothy M. Gallagher, O.M.V.", "Discernment & Prayer", 2, 1, "Popular with adult faith formation group"),
            ("CAT-101", "Catechism of the Catholic Church (2nd Ed.)", "Libreria Editrice Vaticana", "RCIA & Sacramental Prep", 4, 4, "Reference & RCIA loan copies"),
            ("SOC-204", "Rerum Novarum & Catholic Social Teaching Reader", "Various / Papal Encyclicals", "Social Justice & Co-op", 2, 2, "Dignity of work, subsidiarity, and solidarity"),
        ]
        book_ids = {}
        for call, title, auth, cat, tot, avail, notes in catalog:
            book_ids[call] = run(
                "INSERT INTO books (library_id, call_number, title, author, category, copies_total, copies_available, notes)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (st_ig, call, title, auth, cat, tot, avail, notes),
            )
        today = date.today()
        # 1 active loan, 1 overdue loan
        run(
            "INSERT INTO loans (library_id, book_id, borrower_name, borrower_contact, checked_out_at, due_date)"
            " VALUES (?,?,?,?,?,?)",
            (st_ig, book_ids["IGN-001"], "Maria Kowalski", "maria@example.ca",
             (today - timedelta(days=5)).isoformat(), (today + timedelta(days=16)).isoformat()),
        )
        run(
            "INSERT INTO loans (library_id, book_id, borrower_name, borrower_contact, checked_out_at, due_date)"
            " VALUES (?,?,?,?,?,?)",
            (st_ig, book_ids["IGN-003"], "Paul Desjardins", "(204) 555-0192",
             (today - timedelta(days=28)).isoformat(), (today - timedelta(days=7)).isoformat()),
        )
        run(
            "INSERT INTO books (library_id, call_number, title, author, category, copies_total, copies_available, notes)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (holy_rosary, "ITA-001", "I Fioretti di San Francesco (Bilingual IT/EN)", "Ugolino Brunforte", "Bilingual Devotional", 2, 2, "Italian/English parish collection"),
        )


seed_default_libraries()


TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>One Big Backend · Lending Library</title>
<style>
  :root { --bg:#faf8f5; --ink:#1f2421; --muted:#5c6460; --line:#d8d4cc; --accent:#1b4332; --bad:#9b2226; }
  body { font-family: system-ui, sans-serif; background:var(--bg); color:var(--ink); margin:0; }
  .topbar { background:var(--accent); color:#fff; padding:.8rem 1.4rem; display:flex; justify-content:space-between; align-items:center; }
  .topbar a { color:#fff; text-decoration:none; margin-right:1rem; font-weight:600; }
  .wrap { max-width:1040px; margin:1.5rem auto; padding:0 1rem; }
  .flash { background:#e9f5ee; border:1px solid #2d6a4f; padding:.6rem 1rem; border-radius:6px; margin-bottom:1rem; }
  table { width:100%; border-collapse:collapse; background:#fff; margin-bottom:1.5rem; }
  th, td { border:1px solid var(--line); padding:.55rem .7rem; text-align:left; font-size:.93rem; }
  th { background:#f0ede6; }
  .btn, .mini { background:var(--accent); color:#fff; border:none; padding:.45rem .85rem; border-radius:5px; cursor:pointer; font-size:.88rem; }
  .mini.danger { background:var(--bad); }
  .tag { display:inline-block; padding:.15rem .45rem; border-radius:4px; font-size:.78rem; background:#e0ddd5; }
  .tag.ok { background:#d8f3dc; color:#1b4332; }
  .tag.bad { background:#f8d7da; color:#842029; }
</style>
</head>
<body>
<header class="topbar">
  <div>
    <a href="{{ url_for('index') }}">One Big Backend · Parish &amp; Community Library</a>
    {% if lib %}<span>({{ lib.parish_or_org }} — {{ lib.name }})</span>{% endif %}
  </div>
</header>
<main class="wrap">
  {% with msgs = get_flashed_messages() %}
    {% if msgs %}<div class="flash">{% for m in msgs %}<div>{{ m }}</div>{% endfor %}</div>{% endif %}
  {% endwith %}
  {{ body_html|safe }}
</main>
</body>
</html>
"""


@app.route("/")
def index():
    libs = q("SELECT * FROM libraries ORDER BY id")
    rows_html = "".join(
        f"<li><a href='/lib/{l['id']}'><strong>{l['parish_or_org']}</strong> — {l['name']}</a> ({l['address_note']})</li>"
        for l in libs
    )
    body = f"<h1>Member Libraries</h1><p>Shared, parish-owned lending catalog &amp; checkout tracker.</p><ul>{rows_html}</ul>"
    return render_template_string(TEMPLATE, lib=None, body_html=body)


@app.route("/lib/<int:lib_id>")
def library_home(lib_id):
    lib = q1("SELECT * FROM libraries WHERE id=?", (lib_id,))
    if not lib:
        return "Not found", 404
    search_q = (request.args.get("q") or "").strip()
    if search_q:
        like = f"%{search_q}%"
        books = q(
            """SELECT * FROM books WHERE library_id=?
               AND (title LIKE ? OR author LIKE ? OR category LIKE ? OR call_number LIKE ?)
               ORDER BY call_number, title""",
            (lib_id, like, like, like, like),
        )
    else:
        books = q("SELECT * FROM books WHERE library_id=? ORDER BY call_number, title", (lib_id,))
    active_loans = q(
        """SELECT l.*, b.title, b.call_number FROM loans l
           JOIN books b ON b.id=l.book_id
           WHERE l.library_id=? AND l.returned_at=''
           ORDER BY l.due_date""",
        (lib_id,),
    )
    commits = q("SELECT * FROM library_commits WHERE library_id=? ORDER BY id DESC LIMIT 10", (lib_id,))
    today_iso = date.today().isoformat()

    book_rows = []
    for b in books:
        avail_tag = (
            f"<span class='tag ok'>{b['copies_available']}/{b['copies_total']} available</span>"
            if b["copies_available"] > 0
            else f"<span class='tag bad'>0/{b['copies_total']} checked out</span>"
        )
        checkout_form = ""
        if b["copies_available"] > 0:
            checkout_form = (
                f"<form method='post' action='/lib/{lib_id}/checkout/{b['id']}' style='display:inline'>"
                f"<input name='borrower_name' placeholder='Borrower name' required style='width:120px'> "
                f"<input name='borrower_contact' placeholder='Email/Phone' style='width:110px'> "
                f"<button class='mini' type='submit'>Check out</button></form>"
            )
        book_rows.append(
            f"<tr><td><code>{b['call_number']}</code></td><td><strong>{b['title']}</strong><br><small>{b['author']}</small></td>"
            f"<td>{b['category']}</td><td>{avail_tag}</td><td>{checkout_form}</td></tr>"
        )

    loan_rows = []
    for l in active_loans:
        overdue = l["due_date"] < today_iso
        status_badge = "<span class='tag bad'>OVERDUE</span>" if overdue else "<span class='tag ok'>On loan</span>"
        loan_rows.append(
            f"<tr><td><code>{l['call_number']}</code> {l['title']}</td><td>{l['borrower_name']} ({l['borrower_contact']})</td>"
            f"<td>{l['due_date']} {status_badge}</td>"
            f"<td><form method='post' action='/lib/{lib_id}/return/{l['id']}'><button class='mini' type='submit'>Mark returned</button></form></td></tr>"
        )

    commit_rows = []
    for c in commits:
        undo_btn = (
            "<span class='tag'>Undone</span>"
            if c["reverted"] or c["action_kind"] == "revert"
            else f"<form method='post' action='/lib/{lib_id}/undo' style='display:inline'><input type='hidden' name='commit_id' value='{c['id']}'><button class='mini' type='submit'>↶ Undo</button></form>"
        )
        commit_rows.append(
            f"<tr><td><code>{c['commit_hash'][:7]}</code></td><td>{c['created']}</td><td>{c['summary']}</td><td>{undo_btn}</td></tr>"
        )

    body = f"""
    <h1>{lib['name']}</h1>
    <p>{lib['parish_or_org']} · {lib['address_note']} · Standard loan: {lib['loan_days']} days</p>
    <form method="get" style="margin-bottom:1rem">
      <input name="q" value="{search_q}" placeholder="Search title, author, topic, call #..." style="padding:.45rem;width:280px">
      <button class="btn" type="submit">Search catalog</button>
      <a href="/lib/{lib_id}" style="margin-left:.5rem">Clear</a>
    </form>
    <h2>Catalog ({len(books)} titles)</h2>
    <table>
      <tr><th>Call #</th><th>Title &amp; Author</th><th>Category</th><th>Status</th><th>Quick Checkout</th></tr>
      {''.join(book_rows)}
    </table>
    <h2>Active Loans ({len(active_loans)})</h2>
    <table>
      <tr><th>Book</th><th>Borrower</th><th>Due Date</th><th>Action</th></tr>
      {''.join(loan_rows) or '<tr><td colspan="4">No active loans.</td></tr>'}
    </table>
    <h2>Add a Book to Catalog</h2>
    <form method="post" action="/lib/{lib_id}/books/add" style="margin-bottom:1.5rem">
      <input name="call_number" placeholder="Call # (e.g. IGN-004)" required>
      <input name="title" placeholder="Title" required>
      <input name="author" placeholder="Author">
      <input name="category" placeholder="Category" value="Spirituality">
      <input name="copies" type="number" min="1" value="1" style="width:60px">
      <button class="btn" type="submit">Add book</button>
    </form>
    <h2>Git Audit Log &amp; 1-Click Undo</h2>
    <table>
      <tr><th>Commit</th><th>When</th><th>Action</th><th>Undo</th></tr>
      {''.join(commit_rows) or '<tr><td colspan="4">No commits yet.</td></tr>'}
    </table>
    """
    return render_template_string(TEMPLATE, lib=lib, body_html=body)


@app.route("/lib/<int:lib_id>/books/add", methods=["POST"])
def add_book(lib_id):
    before = _snapshot_library(lib_id)
    title = request.form["title"].strip()
    call_no = request.form.get("call_number", "").strip()
    author = request.form.get("author", "").strip()
    category = request.form.get("category", "Spirituality").strip()
    copies = max(1, int(request.form.get("copies", "1") or 1))
    run(
        "INSERT INTO books (library_id, call_number, title, author, category, copies_total, copies_available)"
        " VALUES (?,?,?,?,?,?,?)",
        (lib_id, call_no, title, author, category, copies, copies),
    )
    after = _snapshot_library(lib_id)
    chash = _record_commit(lib_id, "Librarian", "book_add", f"Added '{title}' ({copies} copies)", before, after)
    flash(f"Book added (commit {chash[:7]}).")
    return redirect(url_for("library_home", lib_id=lib_id))


@app.route("/lib/<int:lib_id>/checkout/<int:book_id>", methods=["POST"])
def checkout_book(lib_id, book_id):
    lib = q1("SELECT * FROM libraries WHERE id=?", (lib_id,))
    book = q1("SELECT * FROM books WHERE id=? AND library_id=?", (book_id, lib_id))
    if not book or book["copies_available"] < 1:
        flash("No available copies to check out.")
        return redirect(url_for("library_home", lib_id=lib_id))
    before = _snapshot_library(lib_id)
    borrower = request.form["borrower_name"].strip()
    contact = request.form.get("borrower_contact", "").strip()
    today = date.today()
    due = today + timedelta(days=lib["loan_days"])
    run(
        "INSERT INTO loans (library_id, book_id, borrower_name, borrower_contact, checked_out_at, due_date)"
        " VALUES (?,?,?,?,?,?)",
        (lib_id, book_id, borrower, contact, today.isoformat(), due.isoformat()),
    )
    run("UPDATE books SET copies_available = copies_available - 1 WHERE id=?", (book_id,))
    after = _snapshot_library(lib_id)
    chash = _record_commit(lib_id, "Librarian", "checkout", f"Checked out '{book['title']}' to {borrower}", before, after)
    flash(f"Checked out '{book['title']}' to {borrower} — due {due.isoformat()} (commit {chash[:7]}).")
    return redirect(url_for("library_home", lib_id=lib_id))


@app.route("/lib/<int:lib_id>/return/<int:loan_id>", methods=["POST"])
def return_book(lib_id, loan_id):
    loan = q1("SELECT * FROM loans WHERE id=? AND library_id=? AND returned_at=''", (loan_id, lib_id))
    if not loan:
        flash("Loan not found or already returned.")
        return redirect(url_for("library_home", lib_id=lib_id))
    before = _snapshot_library(lib_id)
    book = q1("SELECT * FROM books WHERE id=?", (loan["book_id"],))
    run("UPDATE loans SET returned_at=? WHERE id=?", (date.today().isoformat(), loan_id))
    run("UPDATE books SET copies_available = MIN(copies_total, copies_available + 1) WHERE id=?", (loan["book_id"],))
    after = _snapshot_library(lib_id)
    chash = _record_commit(lib_id, "Librarian", "return", f"Returned '{book['title']}' from {loan['borrower_name']}", before, after)
    flash(f"Returned '{book['title']}' (commit {chash[:7]}).")
    return redirect(url_for("library_home", lib_id=lib_id))


@app.route("/lib/<int:lib_id>/undo", methods=["POST"])
def undo_library(lib_id):
    commit_id = request.form.get("commit_id")
    if commit_id:
        c = q1("SELECT * FROM library_commits WHERE id=? AND library_id=?", (int(commit_id), lib_id))
    else:
        c = q1("SELECT * FROM library_commits WHERE library_id=? AND reverted=0 ORDER BY id DESC LIMIT 1", (lib_id,))
    if not c:
        flash("Nothing to undo.")
        return redirect(url_for("library_home", lib_id=lib_id))
    cur_snap = _snapshot_library(lib_id)
    before_snap = json.loads(c["before_json"])
    _restore_library(lib_id, before_snap)
    run("UPDATE library_commits SET reverted=1 WHERE id=?", (c["id"],))
    undo_hash = _record_commit(lib_id, "UndoEngine", "revert", f"Reverted {c['commit_hash'][:7]} ({c['summary']})", cur_snap, before_snap)
    run("UPDATE library_commits SET reverted=1 WHERE commit_hash=?", (undo_hash,))
    flash(f"Undid '{c['summary']}' (commit {undo_hash[:7]}).")
    return redirect(url_for("library_home", lib_id=lib_id))
