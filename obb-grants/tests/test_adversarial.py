"""OBB Grants Module 2 — adversarial tenancy/security tests.

These tests ATTACK the app. Module 2 (v2) has NO authentication yet —
the tenant picker is trust-me — so the cross-tenant attacks below are
EXPECTED TO SUCCEED and are recorded as known gaps (v3: real auth),
not as passes. SQL-injection attacks must FAIL (parameterized queries).
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

passed = []
gaps = []


def check(name, cond):
    assert cond, "FAILED: %s" % name
    passed.append(name)


def record_gap(name, note):
    gaps.append((name, note))


D = lambda n: (date.today() + timedelta(days=n)).isoformat()

with A.app.app_context():
    ta = d.run("INSERT INTO tenants (name, kind) VALUES (?,?)", ("Tenant A", "shop"))
    tb = d.run("INSERT INTO tenants (name, kind) VALUES (?,?)", ("Tenant B", "kitchen"))
    d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
          " VALUES (?,?,?,?,?)", (tb, "SECRET B GRANT", "Funder B", D(10), "researching"))

# ---------- G1: cross-tenant read — no auth exists, so this SUCCEEDS ----------
r = client.get("/t/%d/" % tb)
if r.status_code == 200 and b"SECRET B GRANT" in r.data:
    record_gap("G1 cross-tenant read", "ATTACK SUCCEEDS: /t/<B>/ readable with no login "
               "(no auth in v2 — v3 roadmap).")
else:
    check("G1 cross-tenant read blocked", False)

# ---------- G2: cross-tenant write ----------
r = client.post("/t/%d/opps" % tb,
                data={"title": "planted by A", "status": "researching"},
                follow_redirects=False)
with A.app.app_context():
    planted = d.q1("SELECT id FROM opportunities WHERE tenant_id=? AND title=?",
                   (tb, "planted by A"))
if planted:
    record_gap("G2 cross-tenant write", "ATTACK SUCCEEDS: wrote into tenant B "
               "with no login (no auth in v2 — v3 roadmap).")
else:
    check("G2 cross-tenant write blocked", False)

# ---------- G3: SQL injection in stored field ----------
evil = "x'); DROP TABLE opportunities;--"
r = client.post("/t/%d/opps" % ta,
                data={"title": evil, "status": "researching"},
                follow_redirects=False)
with A.app.app_context():
    titles = [o["title"] for o in d.q("SELECT title FROM opportunities")]
    n = d.q1("SELECT COUNT(*) c FROM opportunities")["c"]
check("G3 opportunities table intact after stored injection",
      n >= 3 and evil in titles)

# ---------- G4: SQL injection in URL id ----------
r = client.get("/t/%d/opps/1 OR 1=1" % ta, follow_redirects=False)
check("G4 non-integer URL id rejected (404, no query run)", r.status_code == 404)

# ---------- G5: CSV formula injection ----------
# create an application for tenant A to import into
with A.app.app_context():
    app_id = d.run("INSERT INTO applications (tenant_id, title, status) VALUES (?,?,?)",
                   (ta, "Flow App", "drafting"))
csv_data = "category,description,amount\nSupplies,Paper,=1+1\nTravel,Bus,25\n"
r = client.post("/t/%d/apps/%d/budget/import" % (ta, app_id),
                data={"csv": (io.BytesIO(csv_data.encode()), "budget.csv")},
                content_type="multipart/form-data", follow_redirects=True)
with A.app.app_context():
    sec = d.q1("SELECT body FROM app_sections WHERE application_id=? AND heading='Budget'",
               (app_id,))
body = sec["body"] if sec else ""
check("G5 formula-like amount rejected as non-numeric", "=1+1" not in (body or ""))
check("G5b valid CSV rows still imported", "25" in (body or ""))

# ---------- G6: co-op aggregate leaks nothing even under probing ----------
r = client.get("/coop")
check("G6 /coop hides tenant B title", b"SECRET B GRANT" not in r.data)
check("G6b /coop hides tenant B funder", b"Funder B" not in r.data)

print("ADVERSARIAL (grants): %d defended, %d known gaps." % (len(passed), len(gaps)))
for name in passed:
    print("  PASS  %s" % name)
for name, note in gaps:
    print("  GAP   %s — %s" % (name, note))
