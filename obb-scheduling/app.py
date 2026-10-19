"""One Big Backend — co-op staff scheduling, Module 1 (v2).

Multi-tenant weekly scheduler for independent cannabis retail shops,
with a Bill 56 minimum-staffing rule engine, labor-cost tracking,
shift swaps, availability + time-off, copy-week recurring schedules,
and an in-app notification feed.

v2 changes: real per-tenant login (manager/staff roles), session-based
tenant scoping with hard 403s, multi-week schedules, availability and
time-off requests, one-click copy-week, notifications stub.
"""
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, g, render_template, request, redirect, url_for,
    session, flash, abort,
)
from werkzeug.security import generate_password_hash, check_password_hash

import db as d

app = Flask(__name__)
app.secret_key = os.environ.get("OBB_SECRET", "obb-prototype-dev-key")
if "OBB_SECRET" not in os.environ:
    # Loud on purpose: the fallback key is public (it's in the repo), so any
    # deployment that reaches real users without OBB_SECRET is forgeable.
    import sys
    print("WARNING: OBB_SECRET not set — using the public dev fallback key. "
          "Never serve real users like this.", file=sys.stderr)
app.config["DB_PATH"] = os.environ.get(
    "OBB_DB", os.path.join(os.path.dirname(__file__), "obb.db")
)
app.teardown_appcontext(d.close_db)

# ---- pilot hardening: session cookie flags ----
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Serve over HTTPS in production; set OBB_COOKIE_SECURE=1 there
# (Fly.io sets it in fly.toml). Local HTTP dev keeps it off.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("OBB_COOKIE_SECURE", "0") == "1"

# Schema is created at import time (idempotent) so gunicorn workers —
# which never execute the __main__ block — always see initialized tables.
d.init_db(app)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BUCKET = 30  # minutes per coverage bucket
MAX_WEEK = 7  # schedule horizon: this week + 7 ahead


# ---------- time helpers ----------
def mins_to_str(m):
    h, mm = divmod(int(m), 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mm:02d} {suffix}"


def str_to_mins(s):
    h, m = map(int, s.split(":"))
    return h * 60 + m


def mins_to_input(m):
    return f"{int(m)//60:02d}:{int(m)%60:02d}"


app.jinja_env.filters["tstr"] = mins_to_str
app.jinja_env.filters["tinput"] = mins_to_input


# ---------- data access ----------
def get_shop(shop_id):
    return d.q1("SELECT * FROM shops WHERE id=?", (shop_id,))


def get_user(uid):
    return d.q1("SELECT * FROM users WHERE id=?", (uid,))


def employees(shop_id):
    return d.q("SELECT * FROM employees WHERE shop_id=? ORDER BY name", (shop_id,))


def shifts_for_day(shop_id, day, week=0):
    return d.q(
        """SELECT s.*, e.name AS emp_name, e.hourly_wage
           FROM shifts s JOIN employees e ON e.id = s.employee_id
           WHERE s.shop_id=? AND s.day=? AND s.week=?
           ORDER BY s.start_minutes""",
        (shop_id, day, week),
    )


def shifts_for_week(shop_id, week=0):
    return d.q(
        """SELECT s.*, e.name AS emp_name
           FROM shifts s JOIN employees e ON e.id = s.employee_id
           WHERE s.shop_id=? AND s.week=? ORDER BY s.day, s.start_minutes""",
        (shop_id, week),
    )


def active_rules(shop_id):
    return d.q(
        "SELECT * FROM staffing_rules WHERE shop_id=? AND active=1", (shop_id,)
    )


def user_for_employee(shop_id, employee_id):
    return d.q1(
        "SELECT * FROM users WHERE shop_id=? AND employee_id=?",
        (shop_id, employee_id),
    )


def managers_of(shop_id):
    return d.q(
        "SELECT * FROM users WHERE shop_id=? AND role='manager'", (shop_id,)
    )


def approved_time_off(shop_id, employee_id, week, day):
    return d.q(
        """SELECT * FROM time_off WHERE shop_id=? AND employee_id=?
           AND week=? AND day=? AND status='approved'""",
        (shop_id, employee_id, week, day),
    )


def time_off_conflicts(shop_id, week):
    """Shifts in `week` overlapping an approved time-off. Returns list of dicts."""
    out = []
    for t in d.q(
        "SELECT t.*, e.name AS emp_name FROM time_off t "
        "JOIN employees e ON e.id = t.employee_id "
        "WHERE t.shop_id=? AND t.week=? AND t.status='approved'",
        (shop_id, week),
    ):
        for s in shifts_for_day(shop_id, t["day"], week):
            if s["employee_id"] == t["employee_id"] and \
               s["start_minutes"] < t["end_minutes"] and \
               s["end_minutes"] > t["start_minutes"]:
                out.append({"shift": s, "off": t})
    return out


# ---------- Bill 56 rule engine ----------
def coverage(shop_id, shop, day, week=0):
    """Staff-on-floor count per 30-min bucket for one day of one week."""
    cov = {b: 0 for b in range(shop["open_minutes"], shop["close_minutes"], BUCKET)}
    for s in shifts_for_day(shop_id, day, week):
        for b in cov:
            if s["start_minutes"] < b + BUCKET and s["end_minutes"] > b:
                cov[b] += 1
    return cov


def _merge_buckets(buckets):
    buckets = sorted(buckets)
    segs, cur = [], []
    for b in buckets:
        if cur and b == cur[-1] + BUCKET:
            cur.append(b)
        else:
            if cur:
                segs.append(cur)
            cur = [b]
    if cur:
        segs.append(cur)
    return segs


def check_violations(shop, week=0):
    """Return list of rule violations: {rule, day, start, end, required, actual}."""
    out = []
    for rule in active_rules(shop["id"]):
        days = [int(x) for x in rule["days"].split(",") if x != ""]
        for day in days:
            cov = coverage(shop["id"], shop, day, week)
            bad = [
                b
                for b, n in cov.items()
                if rule["start_minutes"] <= b < rule["end_minutes"]
                and n < rule["min_staff"]
            ]
            for seg in _merge_buckets(bad):
                out.append(
                    {
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "day": day,
                        "day_name": DAYS[day],
                        "start": seg[0],
                        "end": seg[-1] + BUCKET,
                        "required": rule["min_staff"],
                        "actual": min(cov[b] for b in seg),
                    }
                )
    return sorted(out, key=lambda v: (v["day"], v["start"]))


def labor_summary(shop_id, week=0):
    """Per-employee and total hours/cost for one week."""
    rows = d.q(
        """SELECT e.id, e.name, e.role, e.hourly_wage, e.max_hours_week,
                  COALESCE(SUM(s.end_minutes - s.start_minutes), 0) AS mins
           FROM employees e LEFT JOIN shifts s
             ON s.employee_id = e.id AND s.week=?
           WHERE e.shop_id=? GROUP BY e.id ORDER BY e.name""",
        (week, shop_id),
    )
    per_emp, total_h, total_c = [], 0.0, 0.0
    for r in rows:
        h = r["mins"] / 60.0
        c = h * r["hourly_wage"]
        total_h += h
        total_c += c
        per_emp.append(
            {
                "id": r["id"], "name": r["name"], "role": r["role"],
                "wage": r["hourly_wage"], "hours": h, "cost": c,
                "max_hours": r["max_hours_week"],
                "over_max": h > r["max_hours_week"] + 1e-9,
            }
        )
    return per_emp, total_h, total_c


def budget_status(shop, total_cost):
    cap = shop["weekly_budget"] or 0
    if cap <= 0:
        return {"cap": 0, "pct": 0, "state": "none"}
    pct = total_cost / cap * 100
    state = "over" if pct >= 100 else "warn" if pct >= 80 else "ok"
    return {"cap": cap, "pct": pct, "state": state}


# ---------- notifications (in-app stub) ----------
# Seam for later: register callables taking (user_row, kind, text, link)
# to fan out to email/SMS/push. Empty = in-app feed only.
NOTIFICATION_SENDERS = []


def notify(shop_id, user_id, kind, text, link=""):
    if not user_id:
        return
    d.run(
        """INSERT INTO notifications
           (shop_id, user_id, kind, text, link, created, read)
           VALUES (?,?,?,?,?,?,0)""",
        (shop_id, user_id, kind, text, link,
         datetime.now().isoformat(timespec="seconds")),
    )
    user = get_user(user_id)
    for sender in NOTIFICATION_SENDERS:
        try:
            sender(user, kind, text, link)
        except Exception:
            pass  # prototype: senders must never break the request


def notify_managers(shop_id, kind, text, link=""):
    for m in managers_of(shop_id):
        notify(shop_id, m["id"], kind, text, link)


def notify_employee_user(shop_id, employee_id, kind, text, link=""):
    u = user_for_employee(shop_id, employee_id)
    if u:
        notify(shop_id, u["id"], kind, text, link)


def unread_count(user_id):
    r = d.q1(
        "SELECT COUNT(*) AS n FROM notifications WHERE user_id=? AND read=0",
        (user_id,),
    )
    return r["n"] if r else 0


def maybe_notify_violations(shop, week):
    """Tell each manager about this week's violations, at most once per day."""
    if g.user["role"] != "manager":
        return
    violations = check_violations(shop, week)
    if not violations:
        return
    today = datetime.now().date().isoformat()
    for m in managers_of(shop["id"]):
        seen = d.q1(
            """SELECT id FROM notifications
               WHERE user_id=? AND kind='coverage_violation'
               AND substr(created, 1, 10)=? AND read=0""",
            (m["id"], today),
        )
        if not seen:
            v = violations[0]
            notify(
                shop["id"], m["id"], "coverage_violation",
                f"{len(violations)} staffing violation(s) in week {week+1} "
                f"(first: {v['day_name']} {mins_to_str(v['start'])}–"
                f"{mins_to_str(v['end'])}, needs {v['required']}, "
                f"has {v['actual']}).",
                f"/shop/{shop['id']}/schedule?week={week}",
            )


# ---------- auth ----------
@app.before_request
def load_user():
    g.user = None
    g.shop = None
    g.unread = 0
    uid = session.get("user_id")
    if uid:
        u = get_user(uid)
        # session must still match a live user and their shop
        if u and u["shop_id"] == session.get("shop_id"):
            g.user = u
            g.shop = get_shop(u["shop_id"])
            g.unread = unread_count(u["id"])
        else:
            session.clear()


def need_login():
    if not g.user:
        return redirect(url_for("login", next=request.path))
    return None


def guard(shop_id):
    """Login + hard tenant scoping. Cross-tenant access is a 403."""
    r = need_login()
    if r:
        return r
    if not g.shop or g.shop["id"] != int(shop_id):
        abort(403)
    return None


def manager_only():
    if not g.user or g.user["role"] != "manager":
        abort(403)
    return None


@app.errorhandler(403)
def forbidden(_e):
    return render_template("403.html"), 403


def current_week():
    try:
        w = int(request.args.get("week", "0"))
    except ValueError:
        w = 0
    return max(0, min(MAX_WEEK, w))


def own_employee():
    """The logged-in user's linked employee row (staff), or None."""
    if g.user["employee_id"]:
        return d.q1(
            "SELECT * FROM employees WHERE id=? AND shop_id=?",
            (g.user["employee_id"], g.shop["id"]),
        )
    return None


# ---------- public routes ----------
@app.route("/")
def index():
    if g.user:
        return redirect(url_for("dashboard", shop_id=g.shop["id"]))
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard", shop_id=g.shop["id"]))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        u = d.q1("SELECT * FROM users WHERE username=?", (username,))
        if u and check_password_hash(u["password_hash"], password):
            session.clear()
            session["user_id"] = u["id"]
            session["shop_id"] = u["shop_id"]
            nxt = request.form.get("next") or url_for("dashboard", shop_id=u["shop_id"])
            # Post-login redirect must stay on this host (no open redirect).
            if not (nxt.startswith("/") and not nxt.startswith("//")):
                nxt = url_for("dashboard", shop_id=u["shop_id"])
            return redirect(nxt)
        flash("Unknown username or wrong password.")
        return render_template("login.html", next=request.form.get("next", ""))
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/coop")
def coop():
    shops = d.q("SELECT * FROM shops ORDER BY name")
    rows = []
    gt_h = gt_c = 0.0
    for s in shops:
        per_emp, th, tc = labor_summary(s["id"], week=0)
        v = check_violations(s, week=0)
        nshifts = d.q1(
            "SELECT COUNT(*) AS n FROM shifts WHERE shop_id=? AND week=0", (s["id"],)
        )["n"]
        nemp = d.q1(
            "SELECT COUNT(*) AS n FROM employees WHERE shop_id=?", (s["id"],)
        )["n"]
        gt_h += th
        gt_c += tc
        rows.append({
            "name": s["name"], "staff": nemp, "shifts": nshifts,
            "hours": th, "cost": tc, "violations": len(v),
        })
    n = max(len(rows), 1)
    return render_template(
        "coop.html", rows=rows, total_h=gt_h, total_c=gt_c,
        avg_c=gt_c / n, nshops=len(rows),
    )


# ---------- shop routes ----------
@app.route("/shop/<int:shop_id>")
def dashboard(shop_id):
    r = guard(shop_id)
    if r:
        return r
    shop = g.shop
    per_emp, total_h, total_c = labor_summary(shop_id, week=0)
    violations = check_violations(shop, week=0)
    budget = budget_status(shop, total_c)
    today = datetime.now().weekday()  # Mon=0
    todays = shifts_for_day(shop_id, today, week=0)
    pending_swaps = d.q(
        "SELECT COUNT(*) AS n FROM swap_requests WHERE shop_id=? AND status='pending'",
        (shop_id,),
    )[0]["n"]
    return render_template(
        "dashboard.html", shop=shop, per_emp=per_emp, total_h=total_h,
        total_c=total_c, violations=violations, budget=budget,
        todays=todays, today_name=DAYS[today], pending_swaps=pending_swaps,
    )


import hashlib
import json


def _snapshot_week_shifts(shop_id, week):
    """Return a deterministic JSON-serializable list of shifts for (shop_id, week)."""
    rows = d.q(
        """SELECT employee_id, day, week, start_minutes, end_minutes
           FROM shifts WHERE shop_id=? AND week=?
           ORDER BY day, start_minutes, employee_id""",
        (shop_id, week),
    )
    return [dict(r) for r in rows]


def _record_schedule_commit(shop_id, week, action_kind, summary, before_list, after_list):
    """Record a git-style SHA-256 commit of a schedule change (Node 1 + Node 2)."""
    author = g.user["username"] if getattr(g, "user", None) else "system"
    b_json = json.dumps(before_list, sort_keys=True)
    a_json = json.dumps(after_list, sort_keys=True)
    now_iso = datetime.now().isoformat(timespec="seconds")
    raw = f"{shop_id}|{week}|{author}|{action_kind}|{summary}|{b_json}|{a_json}|{now_iso}"
    chash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    d.run(
        """INSERT INTO schedule_commits
           (commit_hash, shop_id, week, author, action_kind, summary, before_json, after_json, created)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (chash, shop_id, week, author, action_kind, summary, b_json, a_json, now_iso),
    )
    return chash


def _restore_week_from_json(shop_id, week, snapshot_json):
    """Atomically restore all shifts in (shop_id, week) from a commit snapshot."""
    items = json.loads(snapshot_json)
    d.run("DELETE FROM shifts WHERE shop_id=? AND week=?", (shop_id, week))
    for it in items:
        d.run(
            "INSERT INTO shifts (shop_id, employee_id, day, week, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?,?)",
            (shop_id, it["employee_id"], it["day"], week, it["start_minutes"], it["end_minutes"]),
        )


@app.route("/shop/<int:shop_id>/schedule")
def schedule(shop_id):
    r = guard(shop_id)
    if r:
        return r
    shop = g.shop
    week = current_week()
    maybe_notify_violations(shop, week)
    wk = [{"day": i, "name": DAYS[i], "shifts": shifts_for_day(shop_id, i, week)}
          for i in range(7)]
    violations = check_violations(shop, week)
    off_conflicts = time_off_conflicts(shop_id, week)
    emps = employees(shop_id)
    last_commit = d.q1(
        """SELECT * FROM schedule_commits
           WHERE shop_id=? AND week=? AND reverted=0
           ORDER BY id DESC LIMIT 1""",
        (shop_id, week),
    )
    return render_template(
        "schedule.html", shop=shop, week=wk, violations=violations,
        off_conflicts=off_conflicts, emps=emps, days=DAYS,
        cur_week=week, max_week=MAX_WEEK, last_commit=last_commit,
    )


def _validate_shift(shop, emp_id, day, start, end, week, ignore_id=None):
    """Shared validation for new/updated shifts. Returns error string or None."""
    if not (0 <= day <= 6):
        return "Invalid day."
    if end <= start:
        return "Shift end must be after shift start (same-day shifts only)."
    if start < shop["open_minutes"] or end > shop["close_minutes"]:
        return (f"Shift must be within store hours "
                f"({mins_to_str(shop['open_minutes'])}–{mins_to_str(shop['close_minutes'])}).")
    emp = d.q1("SELECT id FROM employees WHERE id=? AND shop_id=?",
               (emp_id, shop["id"]))
    if not emp:
        return "Employee not found."
    args = [emp_id, day, week, end, start]
    sql = ("""SELECT id FROM shifts WHERE employee_id=? AND day=? AND week=?
              AND start_minutes < ? AND end_minutes > ?""")
    if ignore_id:
        sql += " AND id != ?"
        args.append(ignore_id)
    if d.q1(sql, args):
        return "That employee already has a shift overlapping that time."
    # approved time-off blocks scheduling
    for t in approved_time_off(shop["id"], emp_id, week, day):
        if start < t["end_minutes"] and end > t["start_minutes"]:
            return (f"Blocked: approved time-off "
                    f"({mins_to_str(t['start_minutes'])}–{mins_to_str(t['end_minutes'])}) "
                    f"covers that window.")
    return None


@app.route("/shop/<int:shop_id>/shifts/add", methods=["POST"])
def add_shift(shop_id):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    shop = g.shop
    week = max(0, min(MAX_WEEK, int(request.form.get("week", "0") or 0)))
    try:
        emp_id = int(request.form["employee_id"])
        day = int(request.form["day"])
        start = str_to_mins(request.form["start"])
        end = str_to_mins(request.form["end"])
    except (KeyError, ValueError):
        flash("Please fill in every field.")
        return redirect(url_for("schedule", shop_id=shop_id, week=week))
    err = _validate_shift(shop, emp_id, day, start, end, week)
    if err:
        flash(err)
        return redirect(url_for("schedule", shop_id=shop_id, week=week))
    before_snap = _snapshot_week_shifts(shop_id, week)
    d.run(
        "INSERT INTO shifts (shop_id, employee_id, day, week, start_minutes, end_minutes)"
        " VALUES (?,?,?,?,?,?)",
        (shop_id, emp_id, day, week, start, end),
    )
    emp = d.q1("SELECT name FROM employees WHERE id=?", (emp_id,))
    after_snap = _snapshot_week_shifts(shop_id, week)
    chash = _record_schedule_commit(
        shop_id, week, "shift_add",
        f"Added {emp['name']} {DAYS[day]} {mins_to_str(start)}–{mins_to_str(end)}",
        before_snap, after_snap,
    )
    notify_employee_user(
        shop_id, emp_id, "shift_assigned",
        f"You were scheduled {DAYS[day]} {mins_to_str(start)}–{mins_to_str(end)}"
        + (f" (week {week+1})" if week else "") + f" at {shop['name']}.",
        f"/shop/{shop_id}/schedule?week={week}",
    )
    flash(f"Shift added (commit {chash[:7]}).")
    return redirect(url_for("schedule", shop_id=shop_id, week=week))


@app.route("/shop/<int:shop_id>/shifts/<int:sid>/delete", methods=["POST"])
def delete_shift(shop_id, sid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    sh = d.q1("SELECT * FROM shifts WHERE id=? AND shop_id=?", (sid, shop_id))
    week = int(request.form.get("week", "0") or 0)
    before_snap = _snapshot_week_shifts(shop_id, sh["week"] if sh else week)
    emp_name = "Staff"
    if sh:
        week = sh["week"]
        emp_row = d.q1("SELECT name FROM employees WHERE id=?", (sh["employee_id"],))
        if emp_row:
            emp_name = emp_row["name"]
        notify_employee_user(
            shop_id, sh["employee_id"], "shift_assigned",
            f"Your shift {DAYS[sh['day']]} {mins_to_str(sh['start_minutes'])}–"
            f"{mins_to_str(sh['end_minutes'])} was removed.",
            f"/shop/{shop_id}/schedule?week={sh['week']}",
        )
    d.run("DELETE FROM shifts WHERE id=? AND shop_id=?", (sid, shop_id))
    d.run(
        "UPDATE swap_requests SET status='denied' WHERE shift_id=? AND status='pending'",
        (sid,),
    )
    if sh:
        after_snap = _snapshot_week_shifts(shop_id, week)
        chash = _record_schedule_commit(
            shop_id, week, "shift_delete",
            f"Deleted {emp_name} {DAYS[sh['day']]} {mins_to_str(sh['start_minutes'])}–{mins_to_str(sh['end_minutes'])}",
            before_snap, after_snap,
        )
        flash(f"Shift deleted (commit {chash[:7]} — click Undo to restore).")
    else:
        flash("Shift deleted.")
    return redirect(url_for("schedule", shop_id=shop_id, week=week))


@app.route("/shop/<int:shop_id>/schedule/clear", methods=["POST"])
def clear_week(shop_id):
    """Nuke all shifts in a week (the 'Killer Demo Moment' on stage) — 100% reversible via Undo."""
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    week = max(0, min(MAX_WEEK, int(request.form.get("week", "0") or 0)))
    before_snap = _snapshot_week_shifts(shop_id, week)
    if not before_snap:
        flash(f"Week {week+1} is already empty.")
        return redirect(url_for("schedule", shop_id=shop_id, week=week))
    d.run("DELETE FROM shifts WHERE shop_id=? AND week=?", (shop_id, week))
    after_snap = _snapshot_week_shifts(shop_id, week)
    chash = _record_schedule_commit(
        shop_id, week, "clear_week",
        f"Cleared all {len(before_snap)} shift(s) in week {week+1}",
        before_snap, after_snap,
    )
    flash(f"Cleared {len(before_snap)} shift(s) in week {week+1} (commit {chash[:7]}). Hit Undo to restore them all!")
    return redirect(url_for("schedule", shop_id=shop_id, week=week))


@app.route("/shop/<int:shop_id>/schedule/undo", methods=["POST"])
def undo_schedule(shop_id):
    """One-click Undo: revert either a specific commit_id or the latest active commit for (shop_id, week)."""
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    commit_id = request.form.get("commit_id")
    week = max(0, min(MAX_WEEK, int(request.form.get("week", "0") or 0)))
    if commit_id:
        commit_row = d.q1(
            "SELECT * FROM schedule_commits WHERE id=? AND shop_id=?",
            (int(commit_id), shop_id),
        )
    else:
        commit_row = d.q1(
            """SELECT * FROM schedule_commits
               WHERE shop_id=? AND week=? AND reverted=0
               ORDER BY id DESC LIMIT 1""",
            (shop_id, week),
        )
    if not commit_row:
        flash("Nothing to undo for this week.")
        return redirect(url_for("schedule", shop_id=shop_id, week=week))
    target_week = commit_row["week"]
    current_snap = _snapshot_week_shifts(shop_id, target_week)
    _restore_week_from_json(shop_id, target_week, commit_row["before_json"])
    restored_snap = _snapshot_week_shifts(shop_id, target_week)
    d.run("UPDATE schedule_commits SET reverted=1 WHERE id=?", (commit_row["id"],))
    undo_hash = _record_schedule_commit(
        shop_id, target_week, "revert",
        f"Reverted commit {commit_row['commit_hash'][:7]} ({commit_row['summary']})",
        current_snap, restored_snap,
    )
    # Mark the revert record itself so repeated 'Undo' walks back cleanly if desired
    d.run("UPDATE schedule_commits SET reverted=1 WHERE commit_hash=?", (undo_hash,))
    flash(f"Undid '{commit_row['summary']}' — restored {len(restored_snap)} shift(s) (commit {undo_hash[:7]}).")
    return redirect(url_for("schedule", shop_id=shop_id, week=target_week))


@app.route("/shop/<int:shop_id>/history")
def schedule_history(shop_id):
    """Git audit log of every schedule change for this shop, with 1-click Undo."""
    r = guard(shop_id)
    if r:
        return r
    commits = d.q(
        "SELECT * FROM schedule_commits WHERE shop_id=? ORDER BY id DESC LIMIT 100",
        (shop_id,),
    )
    enriched = []
    for c in commits:
        cd = dict(c)
        cd["before_count"] = len(json.loads(c["before_json"]))
        cd["after_count"] = len(json.loads(c["after_json"]))
        enriched.append(cd)
    return render_template("history.html", shop=g.shop, commits=enriched)


@app.route("/shop/<int:shop_id>/schedule/copy", methods=["POST"])
def copy_week(shop_id):
    """One-click duplicate of a full week into the next week, skipping conflicts."""
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    try:
        src = max(0, min(MAX_WEEK - 1, int(request.form.get("week", "0") or 0)))
    except ValueError:
        src = 0
    dst = src + 1
    before_snap = _snapshot_week_shifts(shop_id, dst)
    src_shifts = shifts_for_week(shop_id, src)
    copied, skipped = 0, 0
    for s in src_shifts:
        clash = d.q1(
            """SELECT id FROM shifts WHERE employee_id=? AND day=? AND week=?
               AND start_minutes < ? AND end_minutes > ?""",
            (s["employee_id"], s["day"], dst, s["end_minutes"], s["start_minutes"]),
        )
        if clash:
            skipped += 1
            continue
        d.run(
            "INSERT INTO shifts (shop_id, employee_id, day, week, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?,?)",
            (shop_id, s["employee_id"], s["day"], dst,
             s["start_minutes"], s["end_minutes"]),
        )
        copied += 1
    if copied:
        after_snap = _snapshot_week_shifts(shop_id, dst)
        _record_schedule_commit(
            shop_id, dst, "copy_week",
            f"Copied {copied} shift(s) from week {src+1} to week {dst+1}",
            before_snap, after_snap,
        )
    msg = f"Copied {copied} shift(s) from week {src+1} to week {dst+1}."
    if skipped:
        msg += f" Skipped {skipped} conflicting shift(s) already in week {dst+1}."
    flash(msg)
    return redirect(url_for("schedule", shop_id=shop_id, week=dst))


@app.route("/shop/<int:shop_id>/employees", methods=["GET", "POST"])
def employee_list(shop_id):
    r = guard(shop_id)
    if r:
        return r
    if request.method == "POST":
        manager_only()
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip() or "Staff"
        try:
            wage = float(request.form.get("wage", "0"))
            maxh = float(request.form.get("max_hours", "40"))
        except ValueError:
            flash("Wage and max hours must be numbers.")
            return redirect(url_for("employee_list", shop_id=shop_id))
        if not name or wage <= 0:
            flash("Name and a positive wage are required.")
            return redirect(url_for("employee_list", shop_id=shop_id))
        d.run(
            "INSERT INTO employees (shop_id, name, role, hourly_wage, max_hours_week)"
            " VALUES (?,?,?,?,?)",
            (shop_id, name, role, wage, maxh),
        )
        flash(f"Added {name}.")
        return redirect(url_for("employee_list", shop_id=shop_id))
    emps = employees(shop_id)
    per_emp, _, _ = labor_summary(shop_id, week=0)
    hours_by_id = {e["id"]: e for e in per_emp}
    return render_template(
        "employees.html", shop=g.shop, emps=emps, hours_by_id=hours_by_id
    )


@app.route("/shop/<int:shop_id>/employees/<int:eid>/delete", methods=["POST"])
def delete_employee(shop_id, eid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    n = d.q1(
        "SELECT COUNT(*) AS n FROM shifts WHERE employee_id=?", (eid,)
    )["n"]
    if n:
        flash("Remove that employee's shifts first.")
        return redirect(url_for("employee_list", shop_id=shop_id))
    d.run("DELETE FROM employees WHERE id=? AND shop_id=?", (eid, shop_id))
    flash("Employee removed.")
    return redirect(url_for("employee_list", shop_id=shop_id))


@app.route("/shop/<int:shop_id>/rules", methods=["GET", "POST"])
def rule_list(shop_id):
    r = guard(shop_id)
    if r:
        return r
    if request.method == "POST":
        manager_only()
        name = request.form.get("name", "").strip() or "Minimum staffing"
        try:
            min_staff = int(request.form.get("min_staff", "2"))
            start = str_to_mins(request.form["start"])
            end = str_to_mins(request.form["end"])
        except (KeyError, ValueError):
            flash("Please fill in every field correctly.")
            return redirect(url_for("rule_list", shop_id=shop_id))
        days = request.form.getlist("days")
        if not days:
            flash("Pick at least one day.")
            return redirect(url_for("rule_list", shop_id=shop_id))
        if end <= start or min_staff < 1:
            flash("End must be after start; minimum staff at least 1.")
            return redirect(url_for("rule_list", shop_id=shop_id))
        d.run(
            "INSERT INTO staffing_rules (shop_id, name, min_staff, days, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?,?)",
            (shop_id, name, min_staff, ",".join(days), start, end),
        )
        flash("Rule added.")
        return redirect(url_for("rule_list", shop_id=shop_id))
    rules = d.q("SELECT * FROM staffing_rules WHERE shop_id=? ORDER BY id", (shop_id,))
    violations = check_violations(g.shop, week=0)
    return render_template(
        "rules.html", shop=g.shop, rules=rules, violations=violations, days=DAYS
    )


@app.route("/shop/<int:shop_id>/rules/<int:rid>/toggle", methods=["POST"])
def toggle_rule(shop_id, rid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    d.run(
        "UPDATE staffing_rules SET active = 1 - active WHERE id=? AND shop_id=?",
        (rid, shop_id),
    )
    return redirect(url_for("rule_list", shop_id=shop_id))


@app.route("/shop/<int:shop_id>/rules/<int:rid>/delete", methods=["POST"])
def delete_rule(shop_id, rid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    d.run("DELETE FROM staffing_rules WHERE id=? AND shop_id=?", (rid, shop_id))
    flash("Rule deleted.")
    return redirect(url_for("rule_list", shop_id=shop_id))


# ---------- shift swaps ----------
@app.route("/shop/<int:shop_id>/swaps", methods=["GET", "POST"])
def swaps(shop_id):
    r = guard(shop_id)
    if r:
        return r
    if request.method == "POST":
        try:
            shift_id = int(request.form["shift_id"])
            to_id = int(request.form["to_employee_id"])
        except (KeyError, ValueError):
            flash("Pick a shift and a coworker.")
            return redirect(url_for("swaps", shop_id=shop_id))
        sh = d.q1(
            "SELECT * FROM shifts WHERE id=? AND shop_id=?", (shift_id, shop_id)
        )
        if not sh:
            flash("Shift not found.")
            return redirect(url_for("swaps", shop_id=shop_id))
        # staff may only offer their own shifts
        if g.user["role"] != "manager":
            me = own_employee()
            if not me or sh["employee_id"] != me["id"]:
                flash("You can only offer your own shifts.")
                return redirect(url_for("swaps", shop_id=shop_id))
        if sh["employee_id"] == to_id:
            flash("That's already their shift.")
            return redirect(url_for("swaps", shop_id=shop_id))
        clash = d.q1(
            """SELECT id FROM shifts WHERE employee_id=? AND day=? AND week=?
               AND start_minutes < ? AND end_minutes > ?""",
            (to_id, sh["day"], sh["week"], sh["end_minutes"], sh["start_minutes"]),
        )
        if clash:
            flash("That coworker already works an overlapping shift.")
            return redirect(url_for("swaps", shop_id=shop_id))
        rid = d.run(
            """INSERT INTO swap_requests
               (shop_id, shift_id, from_employee_id, to_employee_id, note, created)
               VALUES (?,?,?,?,?,?)""",
            (shop_id, shift_id, sh["employee_id"], to_id,
             request.form.get("note", "").strip(),
             datetime.now().isoformat(timespec="seconds")),
        )
        emp = d.q1("SELECT name FROM employees WHERE id=?", (sh["employee_id"],))
        notify_managers(
            shop_id, "swap_requested",
            f"Swap requested: {emp['name']}'s {DAYS[sh['day']]} shift "
            f"({mins_to_str(sh['start_minutes'])}–{mins_to_str(sh['end_minutes'])}) "
            f"needs approval.",
            f"/shop/{shop_id}/swaps",
        )
        flash("Swap requested — waiting on manager approval.")
        return redirect(url_for("swaps", shop_id=shop_id))
    reqs = d.q(
        """SELECT r.*, s.day, s.week, s.start_minutes, s.end_minutes,
                  f.name AS from_name, t.name AS to_name
           FROM swap_requests r
           JOIN shifts s ON s.id = r.shift_id
           JOIN employees f ON f.id = r.from_employee_id
           JOIN employees t ON t.id = r.to_employee_id
           WHERE r.shop_id=? ORDER BY r.id DESC""",
        (shop_id,),
    )
    if g.user["role"] == "manager":
        shift_pool = shifts_for_week(shop_id, 0)
    else:
        me = own_employee()
        shift_pool = (
            d.q(
                """SELECT s.*, e.name AS emp_name FROM shifts s
                   JOIN employees e ON e.id = s.employee_id
                   WHERE s.shop_id=? AND s.employee_id=? AND s.week=0
                   ORDER BY s.day, s.start_minutes""",
                (shop_id, me["id"]),
            ) if me else []
        )
    emps = employees(shop_id)
    return render_template(
        "swaps.html", shop=g.shop, reqs=reqs, all_shifts=shift_pool,
        emps=emps, days=DAYS,
    )


@app.route("/shop/<int:shop_id>/swaps/<int:rid>/approve", methods=["POST"])
def approve_swap(shop_id, rid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    req = d.q1(
        "SELECT * FROM swap_requests WHERE id=? AND shop_id=? AND status='pending'",
        (rid, shop_id),
    )
    if not req:
        flash("Request not found.")
        return redirect(url_for("swaps", shop_id=shop_id))
    sh = d.q1("SELECT * FROM shifts WHERE id=?", (req["shift_id"],))
    clash = d.q1(
        """SELECT id FROM shifts WHERE employee_id=? AND day=? AND week=? AND id != ?
           AND start_minutes < ? AND end_minutes > ?""",
        (req["to_employee_id"], sh["day"], sh["week"], sh["id"],
         sh["end_minutes"], sh["start_minutes"]),
    )
    if clash:
        flash("Can't approve — that coworker now overlaps.")
        return redirect(url_for("swaps", shop_id=shop_id))
    for t in approved_time_off(shop_id, req["to_employee_id"], sh["week"], sh["day"]):
        if sh["start_minutes"] < t["end_minutes"] and sh["end_minutes"] > t["start_minutes"]:
            flash("Can't approve — that coworker has approved time-off then.")
            return redirect(url_for("swaps", shop_id=shop_id))
    d.run("UPDATE shifts SET employee_id=? WHERE id=?",
          (req["to_employee_id"], req["shift_id"]))
    d.run("UPDATE swap_requests SET status='approved' WHERE id=?", (rid,))
    label = (f"{DAYS[sh['day']]} {mins_to_str(sh['start_minutes'])}–"
             f"{mins_to_str(sh['end_minutes'])}")
    notify_employee_user(
        shop_id, req["from_employee_id"], "swap_approved",
        f"Your swap request for {label} was approved.", f"/shop/{shop_id}/swaps")
    notify_employee_user(
        shop_id, req["to_employee_id"], "swap_approved",
        f"You were given the {label} shift by swap.", f"/shop/{shop_id}/schedule")
    flash("Swap approved.")
    return redirect(url_for("swaps", shop_id=shop_id))


@app.route("/shop/<int:shop_id>/swaps/<int:rid>/deny", methods=["POST"])
def deny_swap(shop_id, rid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    req = d.q1(
        "SELECT * FROM swap_requests WHERE id=? AND shop_id=? AND status='pending'",
        (rid, shop_id),
    )
    d.run(
        "UPDATE swap_requests SET status='denied' WHERE id=? AND shop_id=?",
        (rid, shop_id),
    )
    if req:
        notify_employee_user(
            shop_id, req["from_employee_id"], "swap_denied",
            "Your swap request was denied.", f"/shop/{shop_id}/swaps")
    flash("Swap denied.")
    return redirect(url_for("swaps", shop_id=shop_id))


# ---------- availability ----------
@app.route("/shop/<int:shop_id>/availability", methods=["GET", "POST"])
def availability(shop_id):
    r = guard(shop_id)
    if r:
        return r
    if request.method == "POST":
        try:
            emp_id = int(request.form["employee_id"])
            day = int(request.form["day"])
            start = str_to_mins(request.form["start"])
            end = str_to_mins(request.form["end"])
        except (KeyError, ValueError):
            flash("Please fill in every field.")
            return redirect(url_for("availability", shop_id=shop_id))
        if g.user["role"] != "manager":
            me = own_employee()
            if not me or me["id"] != emp_id:
                flash("You can only set your own availability.")
                return redirect(url_for("availability", shop_id=shop_id))
        if not (0 <= day <= 6) or end <= start:
            flash("Pick a valid day and a window where end is after start.")
            return redirect(url_for("availability", shop_id=shop_id))
        d.run(
            "INSERT INTO availability (shop_id, employee_id, day, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?)",
            (shop_id, emp_id, day, start, end),
        )
        flash("Availability saved.")
        return redirect(url_for("availability", shop_id=shop_id))
    me = own_employee()
    if g.user["role"] == "manager":
        rows = d.q(
            """SELECT a.*, e.name AS emp_name FROM availability a
               JOIN employees e ON e.id = a.employee_id
               WHERE a.shop_id=? ORDER BY e.name, a.day, a.start_minutes""",
            (shop_id,),
        )
    else:
        rows = d.q(
            """SELECT a.*, e.name AS emp_name FROM availability a
               JOIN employees e ON e.id = a.employee_id
               WHERE a.shop_id=? AND a.employee_id=?
               ORDER BY a.day, a.start_minutes""",
            (shop_id, me["id"] if me else -1),
        )
    emps = employees(shop_id) if g.user["role"] == "manager" else ([me] if me else [])
    return render_template(
        "availability.html", shop=g.shop, rows=rows, emps=emps,
        days=DAYS, me=me,
    )


@app.route("/shop/<int:shop_id>/availability/<int:aid>/delete", methods=["POST"])
def delete_availability(shop_id, aid):
    r = guard(shop_id)
    if r:
        return r
    row = d.q1("SELECT * FROM availability WHERE id=? AND shop_id=?", (aid, shop_id))
    if row and g.user["role"] != "manager":
        me = own_employee()
        if not me or row["employee_id"] != me["id"]:
            abort(403)
    d.run("DELETE FROM availability WHERE id=? AND shop_id=?", (aid, shop_id))
    flash("Availability removed.")
    return redirect(url_for("availability", shop_id=shop_id))


# ---------- time off ----------
@app.route("/shop/<int:shop_id>/timeoff", methods=["GET", "POST"])
def timeoff(shop_id):
    r = guard(shop_id)
    if r:
        return r
    if request.method == "POST":
        me = own_employee()
        if g.user["role"] != "manager" and not me:
            flash("Your login isn't linked to a staff member.")
            return redirect(url_for("timeoff", shop_id=shop_id))
        try:
            emp_id = int(request.form["employee_id"]) if g.user["role"] == "manager" \
                else me["id"]
            week = max(0, min(MAX_WEEK, int(request.form.get("week", "0") or 0)))
            day = int(request.form["day"])
            start = str_to_mins(request.form["start"])
            end = str_to_mins(request.form["end"])
        except (KeyError, ValueError):
            flash("Please fill in every field.")
            return redirect(url_for("timeoff", shop_id=shop_id))
        if not (0 <= day <= 6) or end <= start:
            flash("Pick a valid day and a window where end is after start.")
            return redirect(url_for("timeoff", shop_id=shop_id))
        rid = d.run(
            """INSERT INTO time_off
               (shop_id, employee_id, week, day, start_minutes, end_minutes,
                reason, status, created)
               VALUES (?,?,?,?,?,?,?,'pending',?)""",
            (shop_id, emp_id, week, day, start, end,
             request.form.get("reason", "").strip(),
             datetime.now().isoformat(timespec="seconds")),
        )
        emp = d.q1("SELECT name FROM employees WHERE id=?", (emp_id,))
        notify_managers(
            shop_id, "timeoff_requested",
            f"Time-off request: {emp['name']} wants {DAYS[day]} "
            f"{mins_to_str(start)}–{mins_to_str(end)} (week {week+1}) off.",
            f"/shop/{shop_id}/timeoff",
        )
        flash("Time-off requested — waiting on manager approval.")
        return redirect(url_for("timeoff", shop_id=shop_id))
    me = own_employee()
    if g.user["role"] == "manager":
        rows = d.q(
            """SELECT t.*, e.name AS emp_name FROM time_off t
               JOIN employees e ON e.id = t.employee_id
               WHERE t.shop_id=? ORDER BY t.status='pending' DESC, t.week, t.day""",
            (shop_id,),
        )
    else:
        rows = d.q(
            """SELECT t.*, e.name AS emp_name FROM time_off t
               JOIN employees e ON e.id = t.employee_id
               WHERE t.shop_id=? AND t.employee_id=?
               ORDER BY t.week, t.day""",
            (shop_id, me["id"] if me else -1),
        )
    emps = employees(shop_id) if g.user["role"] == "manager" else ([me] if me else [])
    return render_template(
        "timeoff.html", shop=g.shop, rows=rows, emps=emps,
        days=DAYS, me=me, max_week=MAX_WEEK,
    )


@app.route("/shop/<int:shop_id>/timeoff/<int:tid>/approve", methods=["POST"])
def approve_timeoff(shop_id, tid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    t = d.q1(
        "SELECT * FROM time_off WHERE id=? AND shop_id=? AND status='pending'",
        (tid, shop_id),
    )
    if not t:
        flash("Request not found.")
        return redirect(url_for("timeoff", shop_id=shop_id))
    d.run("UPDATE time_off SET status='approved' WHERE id=?", (tid,))
    emp = d.q1("SELECT name FROM employees WHERE id=?", (t["employee_id"],))
    label = (f"{DAYS[t['day']]} {mins_to_str(t['start_minutes'])}–"
             f"{mins_to_str(t['end_minutes'])} (week {t['week']+1})")
    notify_employee_user(
        shop_id, t["employee_id"], "timeoff_approved",
        f"Your time-off request for {label} was approved.",
        f"/shop/{shop_id}/timeoff")
    # warn about already-scheduled shifts this approval now conflicts with
    clashes = [
        s for s in shifts_for_day(shop_id, t["day"], t["week"])
        if s["employee_id"] == t["employee_id"]
        and s["start_minutes"] < t["end_minutes"]
        and s["end_minutes"] > t["start_minutes"]
    ]
    if clashes:
        flash(f"Approved for {emp['name']} — but {len(clashes)} scheduled shift(s) "
              f"overlap that time-off and need reassigning.")
    else:
        flash(f"Time-off approved for {emp['name']}.")
    return redirect(url_for("timeoff", shop_id=shop_id))


@app.route("/shop/<int:shop_id>/timeoff/<int:tid>/deny", methods=["POST"])
def deny_timeoff(shop_id, tid):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    t = d.q1("SELECT * FROM time_off WHERE id=? AND shop_id=?", (tid, shop_id))
    d.run(
        "UPDATE time_off SET status='denied' WHERE id=? AND shop_id=? AND status='pending'",
        (tid, shop_id),
    )
    if t:
        notify_employee_user(
            shop_id, t["employee_id"], "timeoff_denied",
            "Your time-off request was denied.", f"/shop/{shop_id}/timeoff")
    flash("Time-off denied.")
    return redirect(url_for("timeoff", shop_id=shop_id))


# ---------- notifications feed ----------
@app.route("/shop/<int:shop_id>/notifications")
def notifications(shop_id):
    r = guard(shop_id)
    if r:
        return r
    rows = d.q(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100",
        (g.user["id"],),
    )
    return render_template("notifications.html", shop=g.shop, rows=rows)


@app.route("/shop/<int:shop_id>/notifications/read", methods=["POST"])
def notifications_read(shop_id):
    r = guard(shop_id)
    if r:
        return r
    nid = request.form.get("id")
    if nid == "all":
        d.run("UPDATE notifications SET read=1 WHERE user_id=?", (g.user["id"],))
    elif nid:
        d.run(
            "UPDATE notifications SET read=1 WHERE id=? AND user_id=?",
            (nid, g.user["id"]),
        )
    return redirect(url_for("notifications", shop_id=shop_id))


# ---------- settings ----------
@app.route("/shop/<int:shop_id>/settings", methods=["GET", "POST"])
def settings(shop_id):
    r = guard(shop_id)
    if r:
        return r
    manager_only()
    shop = g.shop
    if request.method == "POST":
        name = request.form.get("name", "").strip() or shop["name"]
        try:
            o = str_to_mins(request.form["open"])
            c = str_to_mins(request.form["close"])
            cap = float(request.form.get("budget", "0"))
        except (KeyError, ValueError):
            flash("Check your hours and budget numbers.")
            return redirect(url_for("settings", shop_id=shop_id))
        if c <= o:
            flash("Closing time must be after opening time.")
            return redirect(url_for("settings", shop_id=shop_id))
        d.run(
            "UPDATE shops SET name=?, open_minutes=?, close_minutes=?, weekly_budget=? WHERE id=?",
            (name, o, c, cap, shop_id),
        )
        flash("Shop settings saved.")
        return redirect(url_for("settings", shop_id=shop_id))
    return render_template("settings.html", shop=shop)


if __name__ == "__main__":
    # The Flask dev server is intentionally gone: it must never serve a
    # pilot (debug reloader + single-threaded dev socket). The production
    # entrypoint is gunicorn (see Dockerfile):
    #   gunicorn --workers 2 --bind 0.0.0.0:${PORT:-5057} app:app
    raise SystemExit(
        "Refusing to run the Flask dev server. Use gunicorn: "
        "gunicorn --workers 2 --bind 0.0.0.0:${PORT:-5057} app:app"
    )
