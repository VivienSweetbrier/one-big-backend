"""OBB Grants Module 2 — task-based pilot verification.

Scripts a realistic unassisted user flow through the test client:
create opportunity -> draft application from template -> import a budget
CSV -> log the submission. Every step asserts; no human help.
Runs against a throwaway temp DB.
"""
import io
import os
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
tmp.close()
os.environ["OBB_DB"] = tmp.name

import app as A  # noqa: E402
import db as d  # noqa: E402

A.app.config["TESTING"] = True
d.init_db(A.app)
client = A.app.test_client()

steps = []


def step(name, cond):
    assert cond, "FLOW BROKE at: %s" % name
    steps.append(name)


D = lambda n: (date.today() + timedelta(days=n)).isoformat()

with A.app.app_context():
    t = d.run("INSERT INTO tenants (name, kind) VALUES (?,?)",
              ("Pilot Bakery Co-op", "bakery"))

# 1. create an opportunity
r = client.post("/t/%d/opps" % t,
                data={"title": "Ovens Grant 2026", "funder": "Community Fund",
                      "deadline": D(20), "amount": "8000", "status": "researching"},
                follow_redirects=False)
with A.app.app_context():
    opp = d.q1("SELECT * FROM opportunities WHERE tenant_id=? AND title=?",
               (t, "Ovens Grant 2026"))
step("1. opportunity created (id=%s, deadline %s)" % (opp["id"], opp["deadline"]),
     r.status_code == 302 and opp is not None and opp["status"] == "researching")

# 2. draft an application from the standard template, linked to the opp
r = client.post("/t/%d/apps/new" % t,
                data={"title": "New ovens application",
                      "opportunity_id": str(opp["id"])},
                follow_redirects=False)
with A.app.app_context():
    app_row = d.q1("SELECT * FROM applications WHERE tenant_id=? ORDER BY id DESC", (t,))
    secs = d.q("SELECT heading FROM app_sections WHERE application_id=? ORDER BY position",
               (app_row["id"],))
    opp2 = d.q1("SELECT status FROM opportunities WHERE id=?", (opp["id"],))["status"]
step("2. application drafted from 5-section template (%d sections)" % len(secs),
     r.status_code == 302 and len(secs) == 5)
step("2b. linked opportunity flipped to drafting (status=%s)" % opp2,
     opp2 == "drafting")

# 3. import a budget CSV into the application
csv_data = "category,description,amount\nEquipment,Deck oven,5200\nInstall,Electrician,900\n"
r = client.post("/t/%d/apps/%d/budget/import" % (t, app_row["id"]),
                data={"csv": (io.BytesIO(csv_data.encode()), "budget.csv")},
                content_type="multipart/form-data", follow_redirects=True)
with A.app.app_context():
    sec = d.q1("SELECT body FROM app_sections WHERE application_id=? "
               "AND LOWER(heading) LIKE '%budget%'", (app_row["id"],))
body = sec["body"] or ""
step("3. budget CSV imported (2 line items, total $6100.00)",
     "$6100.00" in body and "Deck oven" in body and "Electrician" in body)

# 4. log the submission
r = client.post("/t/%d/apps/%d/submit" % (t, app_row["id"]), follow_redirects=False)
with A.app.app_context():
    sub = d.q1("SELECT * FROM submissions WHERE tenant_id=? AND application_id=?",
               (t, app_row["id"]))
    app_status = d.q1("SELECT status FROM applications WHERE id=?",
                      (app_row["id"],))["status"]
    opp_status = d.q1("SELECT status FROM opportunities WHERE id=?",
                      (opp["id"],))["status"]
step("4. submission logged (outcome=%s, funder=%s)" % (sub["outcome"], sub["funder"]),
     r.status_code == 302 and sub is not None and sub["outcome"] == "pending"
     and sub["funder"] == "Community Fund")
step("4b. app + opportunity flipped to submitted (%s/%s)" % (app_status, opp_status),
     app_status == "submitted" and opp_status == "submitted")

print("PILOT FLOW (grants): %d steps, all pass with no human help." % len(steps))
for s in steps:
    print("  PASS  %s" % s)
