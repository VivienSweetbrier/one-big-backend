"""One Big Backend — Module 5: The Universal Undo Button (Freemium Web SaaS, Port 5060).

Turns the Universal Semantic Git Engine (obbe_semantic_git.py) into a live,
self-serve Freemium web application for Product Hunt and local small businesses:
- Tier 0 (Community Free Forever — $0/mo): 3 tracked sheets/tables, 30-day Git
  Time-Machine, 1-Click Undo, Formula-Clobber detection, zero hostage data.
- Tier 1 (Co-op Pro & Merge-Guard — $29/mo or Local Barter): Unlimited sheets,
  multi-manager 3-Way Auto-Merge (Sarah + Mike editing the same sheet), instant
  Formula-Clobber SMS/Email alerts, 1-year history.
- Tier 2 (Multi-Site Co-op Patron — $149/mo): Unlimited sites, compliance exports,
  and co-op patronage dividends that subsidize the Community Free Tier.
"""
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime
from flask import Flask, g, render_template_string, request, redirect, url_for, flash

# Import the core semantic git engine from parent directory
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from obbe_semantic_git import (
    SemanticCellAtom,
    FormatSpecificNormalizer,
    SemanticGitEngine,
)

app = Flask(__name__)
app.secret_key = os.environ.get("OBB_SECRET", "obb-prototype-dev-key")
app.config["DB_PATH"] = os.environ.get(
    "OBB_UNDO_DB", os.path.join(os.path.dirname(__file__), "obb_undo.db")
)

FREEMIUM_TIERS = {
    "free": {
        "name": "Community Free Forever",
        "price_label": "$0 / month forever",
        "max_datasets": 3,
        "multi_player_merge": False,
        "badge": "FREE FOREVER",
    },
    "pro": {
        "name": "Co-op Pro (Multi-Manager Merge Guard)",
        "price_label": "$29 / month (or Local Co-op Barter)",
        "max_datasets": 999,
        "multi_player_merge": True,
        "badge": "CO-OP PRO",
    },
    "patron": {
        "name": "Multi-Site Co-op Patron",
        "price_label": "$149 / month (Subsidizes Community Commons)",
        "max_datasets": 9999,
        "multi_player_merge": True,
        "badge": "CO-OP PATRON",
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  owner_note TEXT NOT NULL DEFAULT '',
  tier TEXT NOT NULL DEFAULT 'free',        -- 'free', 'pro', 'patron'
  formulas_saved INTEGER NOT NULL DEFAULT 0,
  undos_performed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS datasets (
  id INTEGER PRIMARY KEY,
  workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  format_kind TEXT NOT NULL DEFAULT 'spreadsheet', -- 'spreadsheet', 'json'
  primary_key_col TEXT NOT NULL DEFAULT 'SKU',
  head_commit_hash TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS undo_commits (
  id INTEGER PRIMARY KEY,
  commit_hash TEXT NOT NULL,
  dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  author TEXT NOT NULL,
  message TEXT NOT NULL,
  merkle_root TEXT NOT NULL,
  atoms_json TEXT NOT NULL,                 -- serialized SemanticCellAtom dict
  formulas_clobbered INTEGER NOT NULL DEFAULT 0,
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


def _serialize_state(state):
    return json.dumps(
        {
            coord: {
                "table_name": a.table_name,
                "row_key": a.row_key,
                "col_key": a.col_key,
                "raw_value": a.raw_value,
                "formula_ast": a.formula_ast,
                "data_type": a.data_type,
            }
            for coord, a in sorted(state.items())
        },
        sort_keys=True,
    )


def _deserialize_state(atoms_json):
    raw = json.loads(atoms_json)
    return {
        coord: SemanticCellAtom(**vals)
        for coord, vals in raw.items()
    }


def _commit_dataset_state(dataset_id, author, message, state, formulas_clobbered=0):
    merkle_root = SemanticGitEngine.compute_tree_merkle_root(state)
    atoms_json = _serialize_state(state)
    now_iso = datetime.now().isoformat(timespec="seconds")
    raw = f"{dataset_id}|{author}|{message}|{merkle_root}|{now_iso}"
    chash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    run(
        """INSERT INTO undo_commits
           (commit_hash, dataset_id, author, message, merkle_root, atoms_json, formulas_clobbered, created)
           VALUES (?,?,?,?,?,?,?,?)""",
        (chash, dataset_id, author, message, merkle_root, atoms_json, formulas_clobbered, now_iso),
    )
    run("UPDATE datasets SET head_commit_hash=? WHERE id=?", (chash, dataset_id))
    return chash


def seed_default_workspaces():
    with app.app_context():
        if q1("SELECT COUNT(*) c FROM workspaces")["c"] > 0:
            return
        # Workspace 1: Community Free Tier (Solo Winnipeg Bakery / Tailor)
        w_free = run(
            "INSERT INTO workspaces (name, owner_note, tier, formulas_saved, undos_performed) VALUES (?,?,?,?,?)",
            ("Portage Ave Tailor & Dry Goods", "Solo shop on Community Free Forever tier", "free", 3, 1),
        )
        ds1 = run(
            "INSERT INTO datasets (workspace_id, name, format_kind, primary_key_col) VALUES (?,?,?,?)",
            (w_free, "Weekly_Inventory_and_Pricing.xlsx", "spreadsheet", "SKU"),
        )
        base_rows = [
            {"SKU": "WOOL-BOLT-01", "Item": "Merino Suiting Bolt", "Qty": "12", "UnitCost": "85.00", "TotalValue": "1020.00"},
            {"SKU": "LINEN-04", "Item": "Irish Linen (Natural)", "Qty": "8", "UnitCost": "62.00", "TotalValue": "496.00"},
            {"SKU": "THREAD-GOLD", "Item": "Heavy Basting Spool", "Qty": "30", "UnitCost": "4.50", "TotalValue": "135.00"},
        ]
        formulas = {
            ("WOOL-BOLT-01", "TotalValue"): "=Qty*UnitCost",
            ("LINEN-04", "TotalValue"): "=Qty*UnitCost",
            ("THREAD-GOLD", "TotalValue"): "=Qty*UnitCost",
        }
        s_base = FormatSpecificNormalizer.from_table_rows("Sheet1", base_rows, "SKU", formulas)
        _commit_dataset_state(ds1, "Owner (Morning Open)", "Initial inventory with active =Qty*UnitCost formulas", s_base)

        # Commit 2: Accidental formula clobber + bad edit so user can immediately test 1-click Undo!
        bad_rows = [
            {"SKU": "WOOL-BOLT-01", "Item": "Merino Suiting Bolt", "Qty": "10", "UnitCost": "85.00", "TotalValue": "850.00"},
            {"SKU": "LINEN-04", "Item": "Irish Linen (Natural)", "Qty": "8", "UnitCost": "62.00", "TotalValue": "9999.00"},
        ]
        bad_formulas = {
            ("WOOL-BOLT-01", "TotalValue"): "=Qty*UnitCost",
            # LINEN-04 formula was clobbered by hardcoded 9999.00, and THREAD-GOLD row was deleted!
        }
        s_bad = FormatSpecificNormalizer.from_table_rows("Sheet1", bad_rows, "SKU", bad_formulas)
        _commit_dataset_state(
            ds1,
            "Late-Night Edit",
            "Updated Wool qty, accidentally deleted Thread row & overwrote Linen formula with 9999.00!",
            s_bad,
            formulas_clobbered=1,
        )

        # Workspace 2: Co-op Pro Tier (Multi-Manager Merge Guard)
        w_pro = run(
            "INSERT INTO workspaces (name, owner_note, tier, formulas_saved, undos_performed) VALUES (?,?,?,?,?)",
            ("Ness Ave Independent Co-op Retailers", "Multi-manager 3-Way Merge Guard + Barter Tier", "pro", 14, 5),
        )
        ds2 = run(
            "INSERT INTO datasets (workspace_id, name, format_kind, primary_key_col) VALUES (?,?,?,?)",
            (w_pro, "Shared_Coop_SKU_Master.csv", "spreadsheet", "SKU"),
        )
        coop_rows = [
            {"SKU": "FLOUR-50LB", "Item": "Organic Bread Flour", "Stock": "40", "UnitCost": "28.50", "TotalValue": "1140.00"},
            {"SKU": "BUTTER-10LB", "Item": "Cultured Butter", "Stock": "15", "UnitCost": "42.00", "TotalValue": "630.00"},
        ]
        coop_f = {
            ("FLOUR-50LB", "TotalValue"): "=Stock*UnitCost",
            ("BUTTER-10LB", "TotalValue"): "=Stock*UnitCost",
        }
        s_coop = FormatSpecificNormalizer.from_table_rows("Inventory", coop_rows, "SKU", coop_f)
        _commit_dataset_state(ds2, "Co-op Sync", "Opening shared SKU sheet", s_coop)


seed_default_workspaces()


BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The Universal Undo Button · One Big Backend</title>
<style>
  :root { --bg:#faf8f5; --ink:#1d232a; --muted:#5a6570; --line:#dcd7cd; --accent:#1b4332; --pro:#0f4c81; --warn:#b45309; --bad:#9b2226; }
  body { font-family: system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--ink); margin:0; line-height:1.45; }
  .topbar { background:var(--accent); color:#fff; padding:.85rem 1.5rem; display:flex; justify-content:space-between; align-items:center; }
  .topbar a { color:#fff; text-decoration:none; font-weight:700; margin-right:1.2rem; }
  .wrap { max-width:1080px; margin:1.5rem auto; padding:0 1rem; }
  .flash { background:#d8f3dc; border:1px solid #2d6a4f; color:#1b4332; padding:.7rem 1rem; border-radius:8px; margin-bottom:1rem; font-weight:600; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(290px, 1fr)); gap:1rem; margin:1.2rem 0; }
  .card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:1.1rem; }
  .badge { display:inline-block; padding:.2rem .55rem; border-radius:5px; font-size:.75rem; font-weight:700; background:#e9ecef; }
  .badge.free { background:#d8f3dc; color:#1b4332; }
  .badge.pro { background:#cfe2ff; color:#084298; }
  .badge.bad { background:#f8d7da; color:#842029; }
  table { width:100%; border-collapse:collapse; background:#fff; margin:1rem 0 1.6rem; }
  th, td { border:1px solid var(--line); padding:.55rem .75rem; text-align:left; font-size:.92rem; }
  th { background:#f2efe9; }
  .btn { background:var(--accent); color:#fff; border:none; padding:.5rem .95rem; border-radius:6px; cursor:pointer; font-weight:600; font-size:.9rem; text-decoration:none; display:inline-block; }
  .btn.warn { background:var(--warn); }
  .btn.danger { background:var(--bad); }
  .btn.pro { background:var(--pro); }
  code { background:#f1eee7; padding:.1rem .35rem; border-radius:4px; font-size:.86rem; }
</style>
</head>
<body>
<header class="topbar">
  <div>
    <a href="/">↶ The Universal Undo Button</a>
    <a href="/pricing">Freemium &amp; Co-op Tiers</a>
  </div>
  <div style="font-size:.88rem">One Big Backend · GNU AGPLv3 · Zero Hostage Data</div>
</header>
<main class="wrap">
  {% with msgs = get_flashed_messages() %}
    {% if msgs %}<div class="flash">{% for m in msgs %}<div>{{ m }}</div>{% endfor %}</div>{% endif %}
  {% endwith %}
  {{ content|safe }}
</main>
</body>
</html>
"""


@app.route("/")
def index():
    workspaces = q("SELECT * FROM workspaces ORDER BY id")
    ws_cards = []
    for w in workspaces:
        tier_info = FREEMIUM_TIERS.get(w["tier"], FREEMIUM_TIERS["free"])
        datasets = q("SELECT * FROM datasets WHERE workspace_id=? ORDER BY id", (w["id"],))
        ds_links = "".join(
            f"<li><a href='/ds/{d['id']}'><strong>{d['name']}</strong></a> (HEAD <code>{d['head_commit_hash'][:7]}</code>)</li>"
            for d in datasets
        )
        ws_cards.append(
            f"<div class='card'>"
            f"<span class='badge {w['tier']}'>{tier_info['badge']}</span>"
            f"<h3 style='margin:.5rem 0 .2rem'>{w['name']}</h3>"
            f"<p style='color:var(--muted);font-size:.88rem;margin:0 0 .8rem'>{w['owner_note']} · {tier_info['price_label']}</p>"
            f"<ul style='padding-left:1.2rem'>{ds_links}</ul>"
            f"<p style='font-size:.85rem;margin-top:.8rem'>🛡️ <strong>{w['formulas_saved']}</strong> formulas guarded · ↶ <strong>{w['undos_performed']}</strong> undos performed</p>"
            f"</div>"
        )
    content = f"""
    <h1>The Universal Undo Button for Small Business</h1>
    <p style="font-size:1.08rem;color:var(--muted)">
      Dropbox and Google Drive save dead binary blobs. <strong>One Big Backend</strong> gives your spreadsheets,
      inventory lists, and POS exports a true <strong>Git time-machine</strong> and a <strong>Formula-Clobber shield</strong>.
      <strong>Free forever</strong> for solo shops and nonprofits; paid or bartered for multi-manager co-op teams.
    </p>
    <div class="cards">{''.join(ws_cards)}</div>
    """
    return render_template_string(BASE_HTML, content=content)


@app.route("/pricing")
def pricing():
    content = """
    <h1>Ethical Freemium: Help Everyone First, Monetize Multiplayer Scale</h1>
    <p style="color:var(--muted)">Protected by Sweetbrier Node 0: We never hold your data hostage. Even on the $0 tier, you get full 1-click export and undo.</p>
    <div class="cards">
      <div class="card">
        <span class="badge free">TIER 0 · COMMUNITY FREE FOREVER</span>
        <h2>$0 / mo</h2>
        <p>For solo tailors, parish volunteers, community kitchens, and independent makers.</p>
        <ul>
          <li>Up to <strong>3 tracked spreadsheets / tables</strong></li>
          <li><strong>1-Click Time-Travel Undo</strong> (30-day commit history)</li>
          <li><strong>Formula-Clobber Alert Banner</strong> (catches when <code>=Qty*UnitCost</code> is overwritten by a number)</li>
          <li>98% storage compression via SHA-256 Cell Atoms</li>
        </ul>
      </div>
      <div class="card">
        <span class="badge pro">TIER 1 · CO-OP PRO &amp; MERGE GUARD</span>
        <h2>$29 / mo <small style="font-size:.8rem">(or Local Barter)</small></h2>
        <p>For busy shops where 2+ managers or staff edit inventory, schedules, and prices at the same time.</p>
        <ul>
          <li><strong>Unlimited tracked sheets, CSVs &amp; JSON feeds</strong></li>
          <li><strong>3-Way Structural Auto-Merge</strong> (Sarah updates Flour stock while Mike updates Butter price — auto-merged cleanly!)</li>
          <li><strong>Instant SMS/Email Formula-Clobber Interception</strong></li>
          <li>1-Year audit history &amp; viral Impact Receipt generator</li>
        </ul>
      </div>
      <div class="card">
        <span class="badge pro">TIER 2 · CREDIT UNION &amp; MULTI-SITE PATRON</span>
        <h2>$149 / mo</h2>
        <p>For credit unions, multi-parish dioceses, unions (CUPE), and multi-location co-ops.</p>
        <ul>
          <li><strong>10 to 60+ locations</strong> under one shared co-op backend</li>
          <li>Cross-branch compliance &amp; audit log exports</li>
          <li><strong>B Corp Co-op Patronage</strong>: Surplus directly subsidizes Tier 0 for Winnipeg small shops!</li>
        </ul>
      </div>
    </div>
    """
    return render_template_string(BASE_HTML, content=content)


@app.route("/ds/<int:ds_id>")
def dataset_view(ds_id):
    ds = q1("SELECT * FROM datasets WHERE id=?", (ds_id,))
    if not ds:
        return "Dataset not found", 404
    ws = q1("SELECT * FROM workspaces WHERE id=?", (ds["workspace_id"],))
    commits = q("SELECT * FROM undo_commits WHERE dataset_id=? ORDER BY id DESC", (ds_id,))
    head_commit = next((c for c in commits if not c["reverted"]), commits[0] if commits else None)
    state = _deserialize_state(head_commit["atoms_json"]) if head_commit else {}

    # Group atoms into rows for clean table display
    rows_by_pk = {}
    cols = set()
    for coord, atom in state.items():
        rows_by_pk.setdefault(atom.row_key, {})[atom.col_key] = atom
        cols.add(atom.col_key)
    sorted_cols = sorted(cols)

    header_cells = f"<th>{ds['primary_key_col']}</th>" + "".join(f"<th>{c}</th>" for c in sorted_cols)
    body_rows = []
    for rk, col_map in sorted(rows_by_pk.items()):
        cells = [f"<td><strong>{rk}</strong></td>"]
        for c in sorted_cols:
            a = col_map.get(c)
            if not a:
                cells.append("<td>—</td>")
            elif a.formula_ast:
                cells.append(f"<td>{a.raw_value} <span class='badge free' title='Formula intact'>{a.formula_ast}</span></td>")
            else:
                cells.append(f"<td>{a.raw_value}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    commit_rows = []
    for idx, c in enumerate(commits):
        clobber_tag = (
            f" <span class='badge bad'>⚠ {c['formulas_clobbered']} FORMULA CLOBBERED</span>"
            if c["formulas_clobbered"] > 0
            else ""
        )
        if c["reverted"]:
            action_html = "<span class='badge'>Undone / Reverted</span>"
        elif idx == 0 and len(commits) > 1:
            action_html = (
                f"<form method='post' action='/ds/{ds_id}/undo' style='display:inline'>"
                f"<input type='hidden' name='target_commit_id' value='{commits[1]['id']}'>"
                f"<input type='hidden' name='bad_commit_id' value='{c['id']}'>"
                f"<button class='btn warn' type='submit'>↶ Undo this commit (Restore {commits[1]['commit_hash'][:7]})</button>"
                f"</form>"
            )
        else:
            action_html = (
                f"<form method='post' action='/ds/{ds_id}/checkout/{c['id']}' style='display:inline'>"
                f"<button class='btn' style='padding:.3rem .65rem;font-size:.8rem' type='submit'>Restore to here</button>"
                f"</form>"
            )
        commit_rows.append(
            f"<tr>"
            f"<td><code>{c['commit_hash'][:7]}</code></td>"
            f"<td>{c['created']}</td>"
            f"<td><strong>{c['author']}</strong></td>"
            f"<td>{c['message']}{clobber_tag}</td>"
            f"<td>{action_html}</td>"
            f"</tr>"
        )

    content = f"""
    <p><a href="/">← All Workspaces</a> · Workspace: <strong>{ws['name']}</strong> (<span class="badge {ws['tier']}">{ws['tier'].upper()}</span>)</p>
    <h1>{ds['name']}</h1>
    <p style="color:var(--muted)">HEAD Commit: <code>{head_commit['commit_hash'] if head_commit else 'none'}</code> · Merkle Root: <code>{head_commit['merkle_root'][:16] if head_commit else ''}...</code></p>

    <h2>Current Live Sheet State ({len(rows_by_pk)} rows)</h2>
    <table>
      <tr>{header_cells}</tr>
      {''.join(body_rows)}
    </table>

    <h2>Git Commit Time-Machine &amp; 1-Click Undo</h2>
    <table>
      <tr><th>Commit</th><th>Timestamp</th><th>Author</th><th>What Changed</th><th>Time-Travel Action</th></tr>
      {''.join(commit_rows)}
    </table>
    """
    return render_template_string(BASE_HTML, content=content)


@app.route("/ds/<int:ds_id>/undo", methods=["POST"])
def undo_latest(ds_id):
    ds = q1("SELECT * FROM datasets WHERE id=?", (ds_id,))
    target_id = int(request.form["target_commit_id"])
    bad_id = int(request.form["bad_commit_id"])
    target_c = q1("SELECT * FROM undo_commits WHERE id=? AND dataset_id=?", (target_id, ds_id))
    bad_c = q1("SELECT * FROM undo_commits WHERE id=? AND dataset_id=?", (bad_id, ds_id))
    if not target_c or not bad_c:
        flash("Commit not found.")
        return redirect(url_for("dataset_view", ds_id=ds_id))

    restored_state = _deserialize_state(target_c["atoms_json"])
    run("UPDATE undo_commits SET reverted=1 WHERE id=?", (bad_id,))
    new_hash = _commit_dataset_state(
        ds_id,
        "Universal Undo Button",
        f"Reverted '{bad_c['message']}' -> Restored state {target_c['commit_hash'][:7]}",
        restored_state,
    )
    run(
        "UPDATE workspaces SET undos_performed = undos_performed + 1, formulas_saved = formulas_saved + ? WHERE id=?",
        (bad_c["formulas_clobbered"], ds["workspace_id"]),
    )
    flash(
        f"↶ BOOM! Undid commit {bad_c['commit_hash'][:7]} — restored deleted rows and recovered {bad_c['formulas_clobbered']} clobbered formula(s)! (New HEAD: {new_hash[:7]})"
    )
    return redirect(url_for("dataset_view", ds_id=ds_id))


@app.route("/ds/<int:ds_id>/checkout/<int:commit_id>", methods=["POST"])
def checkout_commit(ds_id, commit_id):
    ds = q1("SELECT * FROM datasets WHERE id=?", (ds_id,))
    target_c = q1("SELECT * FROM undo_commits WHERE id=? AND dataset_id=?", (commit_id, ds_id))
    if not target_c:
        flash("Commit not found.")
        return redirect(url_for("dataset_view", ds_id=ds_id))
    restored_state = _deserialize_state(target_c["atoms_json"])
    new_hash = _commit_dataset_state(
        ds_id,
        "Time-Travel Restore",
        f"Restored sheet to commit {target_c['commit_hash'][:7]}",
        restored_state,
    )
    run("UPDATE workspaces SET undos_performed = undos_performed + 1 WHERE id=?", (ds["workspace_id"],))
    flash(f"Restored sheet to commit {target_c['commit_hash'][:7]} (New HEAD: {new_hash[:7]}).")
    return redirect(url_for("dataset_view", ds_id=ds_id))
