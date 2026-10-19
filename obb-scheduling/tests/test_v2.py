"""V2 verification: auth isolation, time-off blocking, copy-week,
notifications, plus V1 regression checks. Runs against a temp DB."""
import os
import sys
import tempfile

TMPDB = tempfile.mktemp(suffix=".db")
os.environ["OBB_DB"] = TMPDB
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import runpy
runpy.run_path(os.path.join(os.path.dirname(__file__), "..", "seed.py"),
               run_name="__main__")

import app as A
import db as d

A.app.config["TESTING"] = True
client = A.app.test_client()

BIG, LUC = 1, 2  # seed order: Big Buds first, Lucy's second


def login(username, password="demo-pass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


def logout():
    client.get("/logout")


def ctx():
    return A.app.app_context()


def emp_id(shop, name):
    with ctx():
        return d.q1("SELECT id FROM employees WHERE shop_id=? AND name=?",
                    (shop, name))["id"]


def user_id(username):
    with ctx():
        return d.q1("SELECT id FROM users WHERE username=?", (username,))["id"]


passed = []


def check(name, fn):
    logout()
    try:
        fn()
        passed.append(name)
        print(f"  ok: {name}")
    except AssertionError as e:
        print(f"  FAIL: {name}: {e}")
        raise SystemExit(1)


# ---------- auth ----------
def t_unauth_redirect():
    r = client.get(f"/shop/{BIG}")
    assert r.status_code == 302 and "/login" in r.headers["Location"], r.status_code
check("unauthenticated shop access redirects to login", t_unauth_redirect)


def t_login_ok():
    r = login("marleen")
    assert r.status_code == 302 and f"/shop/{BIG}" in r.headers["Location"], r.status_code
    r = client.get(f"/shop/{BIG}")
    assert r.status_code == 200 and b"Big Buds" in r.data
check("manager login works", t_login_ok)


def t_login_bad():
    r = login("marleen", "wrong")
    assert r.status_code == 200 and b"Unknown username" in r.data
check("wrong password rejected", t_login_bad)


def t_cross_tenant_403():
    login("josh")  # Big Buds staff
    r = client.get(f"/shop/{LUC}")
    assert r.status_code == 403, r.status_code
    r = client.get(f"/shop/{LUC}/schedule")
    assert r.status_code == 403, r.status_code
check("staff cannot see other tenant (403)", t_cross_tenant_403)


def t_staff_cannot_manage():
    login("josh")
    r = client.post(f"/shop/{BIG}/shifts/add",
                    data={"employee_id": 1, "day": 0, "start": "09:00", "end": "10:00"})
    assert r.status_code == 403, r.status_code
    with ctx():
        rid = d.q1("SELECT id FROM swap_requests WHERE shop_id=? AND status='pending'",
                   (BIG,))["id"]
    r = client.post(f"/shop/{BIG}/swaps/{rid}/approve")
    assert r.status_code == 403, r.status_code
    r = client.get(f"/shop/{BIG}/settings")
    assert r.status_code == 403, r.status_code
check("staff blocked from manager-only routes (403)", t_staff_cannot_manage)


def t_lucy_isolation():
    login("lucy")  # Lucy's manager
    r = client.get(f"/shop/{BIG}/employees")
    assert r.status_code == 403, r.status_code
    r = client.get(f"/shop/{LUC}/employees")
    assert r.status_code == 200 and b"Devon" in r.data
check("Lucy's manager isolated from Big Buds", t_lucy_isolation)


# ---------- time off blocks scheduling ----------
def t_timeoff_blocks():
    login("marleen")
    priya = emp_id(BIG, "Priya")
    # manager files time-off for Priya: Sun 10:00–14:00, week 0 (she has no Sun shifts)
    r = client.post(f"/shop/{BIG}/timeoff",
                    data={"employee_id": priya, "week": "0", "day": "6",
                          "start": "10:00", "end": "14:00", "reason": "test"},
                    follow_redirects=False)
    assert r.status_code == 302, r.status_code
    with ctx():
        tid = d.q1("""SELECT id FROM time_off WHERE employee_id=? AND day=6
                      AND status='pending'""", (priya,))["id"]
    client.post(f"/shop/{BIG}/timeoff/{tid}/approve", follow_redirects=False)
    before = None
    with ctx():
        before = d.q1("SELECT COUNT(*) AS n FROM shifts WHERE employee_id=? AND week=0",
                      (priya,))["n"]
    r = client.post(f"/shop/{BIG}/shifts/add",
                    data={"employee_id": priya, "day": "6", "start": "11:00",
                          "end": "13:00", "week": "0"},
                    follow_redirects=True)
    assert b"Blocked: approved time-off" in r.data, r.data[:500]
    with ctx():
        after = d.q1("SELECT COUNT(*) AS n FROM shifts WHERE employee_id=? AND week=0",
                     (priya,))["n"]
    assert before == after, "shift was added despite approved time-off"
check("approved time-off blocks new shifts", t_timeoff_blocks)


def t_timeoff_conflict_warning():
    login("marleen")
    josh = emp_id(BIG, "Josh")
    # Josh HAS a Friday 9–23 shift; approve overlapping time-off -> warning
    with ctx():
        d.run("""INSERT INTO time_off (shop_id, employee_id, week, day,
                 start_minutes, end_minutes, reason, status, created)
                 VALUES (?,?,0,4,540,720,'warn-test','approved','2026-10-14T00:00:00')""",
              (BIG, josh))
    r = client.get(f"/shop/{BIG}/schedule?week=0")
    assert b"Time-off conflicts" in r.data and b"Josh" in r.data
check("schedule page warns on shift/time-off overlap", t_timeoff_conflict_warning)


# ---------- copy week ----------
def t_copy_week():
    login("marleen")
    with ctx():
        w0 = d.q1("SELECT COUNT(*) AS n FROM shifts WHERE shop_id=? AND week=0", (BIG,))["n"]
        w1 = d.q1("SELECT COUNT(*) AS n FROM shifts WHERE shop_id=? AND week=1", (BIG,))["n"]
    assert w1 == 0
    r = client.post(f"/shop/{BIG}/schedule/copy", data={"week": "0"},
                    follow_redirects=True)
    assert b"Copied" in r.data
    with ctx():
        w1 = d.q1("SELECT COUNT(*) AS n FROM shifts WHERE shop_id=? AND week=1", (BIG,))["n"]
    assert w1 == w0, f"week1={w1} week0={w0}"
    # spot-check one copied shift matches source
    with ctx():
        s0 = d.q1("SELECT * FROM shifts WHERE shop_id=? AND week=0 AND day=0 LIMIT 1", (BIG,))
        s1 = d.q1("""SELECT * FROM shifts WHERE shop_id=? AND week=1 AND day=?
                     AND employee_id=? AND start_minutes=? AND end_minutes=?""",
                  (BIG, s0["day"], s0["employee_id"], s0["start_minutes"], s0["end_minutes"]))
    assert s1 is not None
check("copy-week duplicates all shifts to next week", t_copy_week)


def t_copy_week_conflicts():
    login("marleen")
    josh = emp_id(BIG, "Josh")
    # plant a conflicting shift in week 1 (Josh Mon 9–17 already copied there)
    client.post(f"/shop/{BIG}/shifts/add",
                data={"employee_id": josh, "day": "0", "start": "09:00",
                      "end": "10:00", "week": "1"},
                follow_redirects=True)
    r = client.post(f"/shop/{BIG}/schedule/copy", data={"week": "0"},
                    follow_redirects=True)
    assert b"Skipped" in r.data, r.data[:600]
check("copy-week skips conflicts with warning", t_copy_week_conflicts)


# ---------- availability ----------
def t_availability():
    login("josh")
    r = client.post(f"/shop/{BIG}/availability",
                    data={"employee_id": emp_id(BIG, "Josh"), "day": "2",
                          "start": "10:00", "end": "14:00"},
                    follow_redirects=True)
    assert b"Availability saved" in r.data
    # josh cannot set priya's availability
    r = client.post(f"/shop/{BIG}/availability",
                    data={"employee_id": emp_id(BIG, "Priya"), "day": "2",
                          "start": "10:00", "end": "14:00"},
                    follow_redirects=True)
    assert b"only set your own" in r.data
check("staff availability: own ok, others blocked", t_availability)


# ---------- notifications ----------
def t_notifications():
    login("marleen")
    josh, priya = emp_id(BIG, "Josh"), emp_id(BIG, "Priya")
    # give josh a Sunday 9–10 shift (no overlap for priya) then swap it to her
    client.post(f"/shop/{BIG}/shifts/add",
                data={"employee_id": josh, "day": "6", "start": "09:00",
                      "end": "10:00", "week": "0"},
                follow_redirects=True)
    with ctx():
        sh = d.q1("""SELECT id FROM shifts WHERE employee_id=? AND day=6
                     AND start_minutes=540 AND week=0""", (josh,))["id"]
    logout()
    login("josh")
    r = client.post(f"/shop/{BIG}/swaps",
                    data={"shift_id": sh, "to_employee_id": priya, "note": "test"},
                    follow_redirects=True)
    assert b"waiting on manager approval" in r.data
    with ctx():
        n = d.q1("""SELECT * FROM notifications WHERE user_id=? AND kind='swap_requested'
                    AND read=0 ORDER BY id DESC""", (user_id("marleen"),))
    assert n is not None, "manager not notified of swap request"
    logout()
    login("marleen")
    with ctx():
        rid = d.q1("""SELECT id FROM swap_requests WHERE shift_id=? AND status='pending'""",
                   (sh,))["id"]
    r = client.post(f"/shop/{BIG}/swaps/{rid}/approve", follow_redirects=True)
    assert b"Swap approved" in r.data
    with ctx():
        nj = d.q1("""SELECT * FROM notifications WHERE user_id=? AND kind='swap_approved'""",
                  (user_id("josh"),))
        np = d.q1("""SELECT * FROM notifications WHERE user_id=? AND kind='swap_approved'""",
                  (user_id("priya"),))
        new_emp = d.q1("SELECT employee_id FROM shifts WHERE id=?", (sh,))["employee_id"]
    assert nj and np, "swap parties not notified"
    assert new_emp == priya, "shift not reassigned"
    # notifications page + badge
    r = client.get(f"/shop/{BIG}/notifications")
    assert r.status_code == 200 and b"swap requested" in r.data
    r = client.post(f"/shop/{BIG}/notifications/read", data={"id": "all"},
                    follow_redirects=True)
    assert r.status_code == 200
check("notifications: request -> manager, approve -> both parties", t_notifications)


# ---------- V1 regressions ----------
def t_v1_violations():
    login("marleen")
    r = client.get(f"/shop/{BIG}")
    assert b"Fri" in r.data and b"needs 2" in r.data, "Friday violation missing"
check("V1: Big Buds Friday Bill-56 violation still flagged", t_v1_violations)


def t_v1_labor_budget():
    login("marleen")
    r = client.get(f"/shop/{BIG}")
    assert b"Weekly budget" in r.data and b"hours scheduled" in r.data
check("V1: labor summary + budget warnings intact", t_v1_labor_budget)


def t_v1_swap_overlap():
    login("marleen")
    with ctx():
        # Josh Mon 9–17 -> Priya (works Mon 13–23): must be blocked
        sh = d.q1("""SELECT id FROM shifts WHERE shop_id=? AND week=0 AND day=0
                     AND employee_id=? AND start_minutes=540""",
                  (BIG, emp_id(BIG, "Josh"),))["id"]
    r = client.post(f"/shop/{BIG}/swaps",
                    data={"shift_id": sh, "to_employee_id": emp_id(BIG, "Priya")},
                    follow_redirects=True)
    assert b"overlapping shift" in r.data
check("V1: swap overlap check still blocks", t_v1_swap_overlap)


def t_v1_coop_no_leak():
    r = client.get("/coop")
    assert r.status_code == 200
    # NB: "Lucy" is a substring of the shop name "Lucy's" (public), so it
    # can't be substring-checked; every other staff name is unambiguous.
    for name in ["Marleen", "Josh", "Priya", "Sam", "Rae",
                 "Devon", "Aisha", "Theo"]:
        assert name.encode() not in r.data, f"leaked: {name}"
    assert b"Big Buds" in r.data and b"Lucy" in r.data
check("V1: co-op dashboard has zero cross-tenant name leakage", t_v1_coop_no_leak)


def t_v1_rules_crud():
    login("marleen")
    r = client.post(f"/shop/{BIG}/rules",
                    data={"name": "test-rule", "min_staff": "3", "start": "10:00",
                          "end": "12:00", "days": ["0"]},
                    follow_redirects=True)
    assert b"Rule added" in r.data
check("V1: staffing-rule CRUD intact", t_v1_rules_crud)


print(f"\nALL {len(passed)} CHECKS PASSED")
