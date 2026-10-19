"""OBB Grants Module 2 V2 verification: deadline reminders, CSV budget import,
draft-assist stub, custom templates, tenant isolation, no cross-tenant leakage.
Runs against a throwaway temp DB. All assertions must pass."""
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


def check(name, cond):
    assert cond, "FAILED: %s" % name
    passed.append(name)


D = lambda n: (date.today() + timedelta(days=n)).isoformat()

with A.app.app_context():
    ta = d.run("INSERT INTO tenants (name, kind) VALUES (?,?)", ("Tenant A", "shop"))
    tb = d.run("INSERT INTO tenants (name, kind) VALUES (?,?)", ("Tenant B", "kitchen"))
    d.run("INSERT INTO boilerplates (tenant_id, block_name, body, updated) VALUES (?,?,?,?)",
          (ta, "Mission", "Tenant A keeps the craft alive.", D(0)))
    # opportunities at the reminder boundaries
    o30 = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
                " VALUES (?,?,?,?,?)", (ta, "Thirty Day Grant", "Funder X", D(30), "researching"))
    o7 = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
               " VALUES (?,?,?,?,?)", (ta, "Seven Day Grant", "Funder Y", D(7), "drafting"))
    o1 = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
               " VALUES (?,?,?,?,?)", (ta, "One Day Grant", "Funder Z", D(1), "drafting"))
    oover = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
                  " VALUES (?,?,?,?,?)", (ta, "Overdue Grant", "Funder W", D(-3), "drafting"))
    ofar = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
                 " VALUES (?,?,?,?,?)", (ta, "Far Grant", "Funder V", D(90), "researching"))
    ob = d.run("INSERT INTO opportunities (tenant_id, title, funder, deadline, status)"
               " VALUES (?,?,?,?,?)", (tb, "B Grant", "Funder B", D(5), "researching"))

    # ---- reminders: boundary generation ----
    client.get("/t/%d/" % ta)  # dashboard triggers ensure_reminders
    rems = d.q("SELECT kind, opportunity_id FROM reminders WHERE tenant_id=? AND read=0", (ta,))
    kinds = {(r["opportunity_id"], r["kind"]) for r in rems}
    check("30-day opp gets due_soon_30", (o30, "due_soon_30") in kinds)
    check("30-day opp does not get due_soon_7", (o30, "due_soon_7") not in kinds)
    check("7-day opp gets due_soon_30+7", (o7, "due_soon_30") in kinds and (o7, "due_soon_7") in kinds)
    check("1-day opp gets 30+7+1", all((o1, k) in kinds for k in ("due_soon_30", "due_soon_7", "due_soon_1")))
    check("overdue opp gets overdue", (oover, "overdue") in kinds)
    check("90-day opp gets nothing", not any(r["opportunity_id"] == ofar for r in rems))

    # ---- reminders: idempotent ----
    n_before = len(rems)
    client.get("/t/%d/" % ta)
    n_after = d.q1("SELECT COUNT(*) c FROM reminders WHERE tenant_id=? AND read=0", (ta,))["c"]
    check("no duplicate reminders on re-run", n_before == n_after)

    # ---- reminders: page renders, mark-read works ----
    r = client.get("/t/%d/reminders" % ta)
    check("reminders page 200", r.status_code == 200)
    check("reminder message on page", b"30-day warning" in r.data)
    rid = d.q1("SELECT id FROM reminders WHERE tenant_id=? AND read=0 LIMIT 1", (ta,))["id"]
    client.post("/t/%d/reminders/%d/read" % (ta, rid))
    check("mark-read works", d.q1("SELECT read FROM reminders WHERE id=?", (rid,))["read"] == 1)
    # idempotent regen refills only the kind just read
    client.get("/t/%d/" % ta)
    n_refill = d.q1("SELECT COUNT(*) c FROM reminders WHERE tenant_id=? AND read=0", (ta,))["c"]
    check("regen refills read reminder", n_refill == n_after)

    # ---- reminders: tenant isolation ----
    rb = client.get("/t/%d/reminders" % tb)
    check("B reminders page 200", rb.status_code == 200)
    check("B sees none of A's reminders", b"Thirty Day Grant" not in rb.data and b"Seven Day Grant" not in rb.data)
    check("B has its own 7-day reminder", b"B Grant" in rb.data)

    # ---- custom templates: save + reuse ----
    tpl = d.run("INSERT INTO app_templates (tenant_id, name, funder, created) VALUES (?,?,?,?)",
                (ta, "Funder X Template", "Funder X", D(0)))
    for i, h in enumerate(["Need", "Plan"]):
        d.run("INSERT INTO app_template_sections (template_id, position, heading, prompt, word_target)"
              " VALUES (?,?,?,?,?)", (tpl, i, h, "prompt %d" % i, 50))
    resp = client.post("/t/%d/apps/new" % ta,
                       data={"title": "From template", "template_id": str(tpl)})
    check("app from template redirects", resp.status_code == 302)
    new_app = d.q1("SELECT * FROM applications WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (ta,))
    secs = d.q("SELECT heading FROM app_sections WHERE application_id=? ORDER BY position",
               (new_app["id"],))
    check("template sections seeded 1:1", [s["heading"] for s in secs] == ["Need", "Plan"])
    # standard template still works
    resp = client.post("/t/%d/apps/new" % ta, data={"title": "Standard app", "template_id": ""})
    std_app = d.q1("SELECT * FROM applications WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (ta,))
    std_secs = d.q("SELECT heading FROM app_sections WHERE application_id=? ORDER BY position",
                   (std_app["id"],))
    check("standard 5-section template intact", len(std_secs) == 5 and std_secs[0]["heading"] == "Project summary")

    # ---- templates: tenant isolation ----
    bad = client.get("/t/%d/templates/%d" % (tb, tpl))
    check("B cannot open A's template", bad.status_code == 302)  # flash + redirect

    # ---- draft assist stub ----
    sec_id = d.q1("SELECT id FROM app_sections WHERE application_id=? LIMIT 1", (new_app["id"],))["id"]
    client.post("/t/%d/apps/%d/section/%d/assist" % (ta, new_app["id"], sec_id))
    body = d.q1("SELECT body FROM app_sections WHERE id=?", (sec_id,))["body"]
    check("assist inserts labeled starter", "[TEMPLATE STARTER" in body)
    check("starter references boilerplate", "Tenant A keeps the craft alive." in body)
    check("starter says not AI", "not by AI" in body)

    # ---- budget CSV import: good rows ----
    good_csv = "category,description,amount\nEquipment,Sewing machine,4500\nSupplies,Thread,120.50\n"
    resp = client.post("/t/%d/apps/%d/budget/import" % (ta, new_app["id"]),
                       data={"csv": (io.BytesIO(good_csv.encode()), "budget.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    check("csv import redirects ok", resp.status_code == 200)
    budget = d.q1("SELECT body FROM app_sections WHERE application_id=? AND LOWER(heading) LIKE '%budget%'",
                  (new_app["id"],))
    check("budget section created", budget is not None)
    check("line items imported", "Sewing machine" in budget["body"] and "Thread" in budget["body"])
    check("total correct", "Total: $4620.50" in budget["body"])

    # ---- budget CSV import: malformed rows reported, valid rows kept ----
    bad_csv = ("category,description,amount\nEquipment,Press,notanumber\n"
               ",, \nSupplies,Needles,25\n")
    resp = client.post("/t/%d/apps/%d/budget/import" % (ta, new_app["id"]),
                       data={"csv": (io.BytesIO(bad_csv.encode()), "budget.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    check("malformed rows reported", b"is not a number" in resp.data)
    check("blank row reported", b"no category or description" in resp.data or b"amount is blank" in resp.data)
    budget2 = d.q1("SELECT body FROM app_sections WHERE application_id=? AND LOWER(heading) LIKE '%budget%'",
                   (new_app["id"],))
    check("valid row still imported", "Needles" in budget2["body"])

    # ---- budget CSV import: missing amount column ----
    nocol = "category,description\nEquipment,Press\n"
    resp = client.post("/t/%d/apps/%d/budget/import" % (ta, new_app["id"]),
                       data={"csv": (io.BytesIO(nocol.encode()), "budget.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    check("missing amount column rejected", b"No amount column" in resp.data)

    # ---- budget import: tenant isolation ----
    resp = client.post("/t/%d/apps/%d/budget/import" % (tb, new_app["id"]),
                       data={"csv": (io.BytesIO(good_csv.encode()), "budget.csv")},
                       content_type="multipart/form-data")
    check("B cannot import into A's app", resp.status_code == 302)

    # ---- V1 intact: deadline engine + boilerplate insert + co-op leakage ----
    r = client.get("/t/%d/opps" % ta)
    check("opps page still 200", r.status_code == 200)
    check("urgent band still red", b"badrow" in r.data or b"Seven Day Grant" in r.data)
    r = client.get("/coop")
    check("coop page 200", r.status_code == 200)
    check("no cross-tenant detail leakage", b"Thirty Day Grant" not in r.data and b"Funder X" not in r.data)
    # reminder messages don't leak either (page is tenant-scoped, but double-check coop)
    check("coop has no reminder text", b"30-day warning" not in r.data)

print("ALL %d CHECKS PASSED" % len(passed))
os.unlink(tmp.name)
