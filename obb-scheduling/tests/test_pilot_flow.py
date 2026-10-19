"""OBB Scheduling Module 1 — task-based pilot verification.

Scripts a realistic unassisted user flow through the test client:
manager logs in -> creates a week (assigns shifts) -> staff requests
time off -> manager approves -> approved time-off blocks a conflicting
shift -> copy-week duplicates the week. Every step asserts; no human help.
Runs against a throwaway temp DB.
"""
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

steps = []


def step(name, cond):
    assert cond, "FLOW BROKE at: %s" % name
    steps.append(name)


def login(u, p="demo-pass"):
    return client.post("/login", data={"username": u, "password": p},
                       follow_redirects=False)


def logout():
    client.get("/logout")


def ctx():
    return A.app.app_context()


with ctx():
    josh = d.q1("SELECT id FROM employees WHERE shop_id=1 AND name='Josh'")["id"]
    priya = d.q1("SELECT id FROM employees WHERE shop_id=1 AND name='Priya'")["id"]

# 1. manager logs in
r = login("marleen")
step("1. manager marleen logs in (302 to /shop/1)",
     r.status_code == 302 and r.headers["Location"].endswith("/shop/1"))

# 2. manager assigns Josh a shift on his first shift-free day (week 0)
with ctx():
    busy_days = {r["day"] for r in d.q(
        "SELECT day FROM shifts WHERE shop_id=1 AND week=0 AND employee_id=?", (josh,))}
    shift_day = next(dd for dd in range(7) if dd not in busy_days)
    before = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=0")["c"]
r = client.post("/shop/1/shifts/add",
                data={"employee_id": str(josh), "day": str(shift_day), "week": "0",
                      "start": "09:00", "end": "17:00"}, follow_redirects=False)
with ctx():
    after = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=0")["c"]
    new_shift = d.q1("SELECT id FROM shifts WHERE shop_id=1 AND week=0"
                     " AND employee_id=? AND day=?", (josh, shift_day))
step("2. manager assigns Josh a shift on day %d (count %d -> %d)"
     % (shift_day, before, after),
     r.status_code == 302 and after == before + 1 and new_shift is not None)
logout()

# 3. staff requests a week-1 day off (week 1 is empty, so no shift overlap
#    can confuse the time-off block test later)
r = login("josh")
step("3. staff josh logs in", r.status_code == 302)
r = client.post("/shop/1/timeoff",
                data={"week": "1", "day": "2", "start": "09:00", "end": "17:00",
                      "reason": "Dentist appointment"}, follow_redirects=False)
with ctx():
    to = d.q1("SELECT * FROM time_off WHERE shop_id=1 AND employee_id=? AND week=1"
              " AND day=2 ORDER BY id DESC", (josh,))
step("3b. time-off request recorded as pending (week 2, day 2)",
     r.status_code == 302 and to is not None and to["status"] == "pending")
logout()

# 4. manager approves
login("marleen")
r = client.post("/shop/1/timeoff/%d/approve" % to["id"], follow_redirects=False)
with ctx():
    to2 = d.q1("SELECT status FROM time_off WHERE id=?", (to["id"],))["status"]
step("4. manager approves the request (status=%s)" % to2,
     r.status_code == 302 and to2 == "approved")

# 5. approved time-off blocks a conflicting new shift (week 1, day 2 is
#    shift-free, so the time-off check is what fires)
with ctx():
    n0 = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=1")["c"]
r = client.post("/shop/1/shifts/add",
                data={"employee_id": str(josh), "day": "2", "week": "1",
                      "start": "10:00", "end": "14:00"}, follow_redirects=True)
with ctx():
    n1 = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=1")["c"]
step("5. conflicting shift blocked by approved time-off (count %d -> %d)" % (n0, n1),
     n1 == n0 and b"time-off" in r.data)

# 6. copy week 0 -> week 1
with ctx():
    w1_before = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=1")["c"]
r = client.post("/shop/1/schedule/copy", data={"week": "0"}, follow_redirects=False)
with ctx():
    w1_after = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=1")["c"]
    w0 = d.q1("SELECT COUNT(*) c FROM shifts WHERE shop_id=1 AND week=0")["c"]
step("6. copy-week duplicates week 0 (%d shifts) into week 1 (%d -> %d)"
     % (w0, w1_before, w1_after),
     r.status_code == 302 and w1_after == w1_before + w0)
logout()

print("PILOT FLOW (scheduling): %d steps, all pass with no human help." % len(steps))
for s in steps:
    print("  PASS  %s" % s)
