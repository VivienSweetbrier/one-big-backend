"""One Big Backend — grant-writing automation, Module 2 (prototype).

Multi-tenant grant pipeline for co-op member orgs: opportunity tracker,
boilerplate library, deadline calendar with warnings, collaborative
application drafter, submission log, and a co-op aggregate dashboard
that never leaks one tenant's details to another.
"""
import os
from datetime import date, datetime

from flask import Flask, g, render_template, request, redirect, url_for, flash

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

OPP_STATUSES = ["researching", "drafting", "submitted", "won", "lost"]
ACTIVE_OPP = ("researching", "drafting")
SUB_OUTCOMES = ["pending", "won", "lost"]

# Default application template: sections every grant application needs.
TEMPLATE_SECTIONS = [
    ("Project summary", "What will you do with the money? Be concrete: who, what, where, when.", 150),
    ("Organizational background", "Who are you? History, track record, why you are the ones to do this.", 200),
    ("Community impact", "Who benefits, and how will you know it worked?", 200),
    ("Budget", "Line items: what the money buys. Tie each line to the project summary.", 150),
    ("Contact", "Who the funder calls with questions.", 50),
]


# ---------- deadline engine ----------
def parse_deadline(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def deadline_band(opp):
    """Return (days_until, band) for an opportunity row. band in
    urgent/soon/ok/past/none."""
    dl = parse_deadline(opp["deadline"])
    if dl is None:
        return None, "none"
    days = (dl - date.today()).days
    if days < 0:
        return days, "past"
    if days <= 7:
        return days, "urgent"
    if days <= 30:
        return days, "soon"
    return days, "ok"


def with_bands(opps):
    out = []
    for o in opps:
        days, band = deadline_band(o)
        out.append((dict(o), days, band))
    return out


# ---------- deadline reminders (v2) ----------
# Clean seam for real delivery later: each entry is a callable taking
# (tenant_row, reminder_row). In-app feed is the v1/v2 delivery channel;
# wire email/SMS here without touching routes or templates.
NOTIFICATION_SENDERS = []

REMINDER_WINDOWS = [("due_soon_30", 30), ("due_soon_7", 7), ("due_soon_1", 1)]


def reminder_message(opp, kind, days):
    label = {"due_soon_30": "30-day warning", "due_soon_7": "7-day warning",
             "due_soon_1": "1-day warning", "overdue": "OVERDUE"}[kind]
    when = ("deadline passed %d days ago" % abs(days)) if kind == "overdue" \
        else ("due in %d day%s" % (days, "" if days == 1 else "s"))
    return "%s: '%s'%s — %s." % (
        label, opp["title"],
        (" (%s)" % opp["funder"]) if opp["funder"] else "", when)


def ensure_reminders(tenant_id):
    """Generate one unread reminder per (opportunity, kind) when an active
    opportunity crosses a 30/7/1-day boundary or goes overdue. Idempotent:
    re-running never duplicates an unread reminder."""
    today = date.today()
    for o in opportunities(tenant_id, ACTIVE_OPP):
        days, band = deadline_band(o)
        if days is None:
            continue
        kinds = ["overdue"] if band == "past" else [k for k, n in REMINDER_WINDOWS if days <= n]
        for kind in kinds:
            dup = d.q1(
                "SELECT id FROM reminders WHERE tenant_id=? AND opportunity_id=? AND kind=? AND read=0",
                (tenant_id, o["id"], kind),
            )
            if not dup:
                rid = d.run(
                    "INSERT INTO reminders (tenant_id, opportunity_id, kind, message, created)"
                    " VALUES (?,?,?,?,?)",
                    (tenant_id, o["id"], kind, reminder_message(o, kind, days),
                     today.isoformat()),
                )
                for sender in NOTIFICATION_SENDERS:
                    try:
                        sender(get_tenant(tenant_id), d.q1("SELECT * FROM reminders WHERE id=?", (rid,)))
                    except Exception:
                        pass  # senders must never break the in-app feed


def unread_reminders(tenant_id):
    return d.q1(
        "SELECT COUNT(*) c FROM reminders WHERE tenant_id=? AND read=0", (tenant_id,)
    )["c"]


# ---------- data access ----------
def get_tenant(tenant_id):
    return d.q1("SELECT * FROM tenants WHERE id=?", (tenant_id,))


def opportunities(tenant_id, statuses=None):
    sql = "SELECT * FROM opportunities WHERE tenant_id=? "
    args = [tenant_id]
    if statuses:
        sql += "AND status IN (%s) " % ",".join("?" * len(statuses))
        args += list(statuses)
    sql += "ORDER BY CASE WHEN deadline='' THEN 1 ELSE 0 END, deadline"
    return d.q(sql, args)


def word_count(text):
    return len((text or "").split())


# ---------- request plumbing ----------
@app.before_request
def load_tenant():
    g.tenant = None
    g.unread_reminders = 0
    if request.view_args and "tenant_id" in request.view_args:
        g.tenant = get_tenant(request.view_args["tenant_id"])
        if g.tenant is None:
            flash("Unknown tenant.")
            return redirect(url_for("index"))
        g.unread_reminders = unread_reminders(g.tenant["id"])


@app.route("/")
def index():
    tenants = d.q("SELECT * FROM tenants ORDER BY name")
    return render_template("index.html", tenants=tenants)


# ---------- dashboard ----------
@app.route("/t/<int:tenant_id>/")
def dashboard(tenant_id):
    ensure_reminders(tenant_id)
    opps = with_bands(opportunities(tenant_id, ACTIVE_OPP))
    urgent = [o for o in opps if o[2] in ("urgent", "past")]
    soon = [o for o in opps if o[2] == "soon"]
    n_apps = d.q1(
        "SELECT COUNT(*) c FROM applications WHERE tenant_id=? AND status != 'submitted'",
        (tenant_id,),
    )["c"]
    subs = d.q1(
        "SELECT COUNT(*) c, COALESCE(SUM(CASE WHEN outcome='won' THEN award_amount ELSE 0 END),0) won "
        "FROM submissions WHERE tenant_id=?",
        (tenant_id,),
    )
    return render_template(
        "dashboard.html", urgent=urgent, soon=soon, n_apps=n_apps,
        n_subs=subs["c"], won=subs["won"],
    )


# ---------- opportunities ----------
@app.route("/t/<int:tenant_id>/opps", methods=["GET", "POST"])
def opp_list(tenant_id):
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.")
        else:
            d.run(
                "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
                " eligibility_notes, status, notes) VALUES (?,?,?,?,?,?,?,?)",
                (tenant_id, title, request.form.get("funder", "").strip(),
                 request.form.get("deadline", "").strip(),
                 float(request.form.get("amount") or 0),
                 request.form.get("eligibility_notes", "").strip(),
                 request.form.get("status", "researching"), request.form.get("notes", "").strip()),
            )
            flash("Opportunity added.")
        return redirect(url_for("opp_list", tenant_id=tenant_id))
    opps = with_bands(opportunities(tenant_id))
    return render_template("opportunities.html", opps=opps, statuses=OPP_STATUSES)


@app.route("/t/<int:tenant_id>/opps/<int:opp_id>", methods=["GET", "POST"])
def opp_detail(tenant_id, opp_id):
    opp = d.q1("SELECT * FROM opportunities WHERE id=? AND tenant_id=?", (opp_id, tenant_id))
    if not opp:
        flash("Opportunity not found.")
        return redirect(url_for("opp_list", tenant_id=tenant_id))
    if request.method == "POST":
        if "delete" in request.form:
            d.run("DELETE FROM opportunities WHERE id=?", (opp_id,))
            flash("Opportunity deleted.")
            return redirect(url_for("opp_list", tenant_id=tenant_id))
        d.run(
            "UPDATE opportunities SET title=?, funder=?, deadline=?, amount=?,"
            " eligibility_notes=?, status=?, notes=? WHERE id=?",
            (request.form.get("title", "").strip(), request.form.get("funder", "").strip(),
             request.form.get("deadline", "").strip(), float(request.form.get("amount") or 0),
             request.form.get("eligibility_notes", "").strip(),
             request.form.get("status", "researching"), request.form.get("notes", "").strip(), opp_id),
        )
        flash("Opportunity updated.")
        return redirect(url_for("opp_detail", tenant_id=tenant_id, opp_id=opp_id))
    days, band = deadline_band(opp)
    apps = d.q("SELECT * FROM applications WHERE opportunity_id=? ORDER BY id", (opp_id,))
    return render_template("opportunity.html", opp=opp, days=days, band=band,
                           apps=apps, statuses=OPP_STATUSES)


# ---------- boilerplate library ----------
@app.route("/t/<int:tenant_id>/blocks", methods=["GET", "POST"])
def blocks(tenant_id):
    if request.method == "POST":
        name = request.form.get("block_name", "").strip()
        if not name:
            flash("Block name is required.")
        else:
            d.run(
                "INSERT INTO boilerplates (tenant_id, block_name, body, updated)"
                " VALUES (?,?,?,?)",
                (tenant_id, name, request.form.get("body", "").strip(),
                 date.today().isoformat()),
            )
            flash("Boilerplate block saved.")
        return redirect(url_for("blocks", tenant_id=tenant_id))
    rows = d.q("SELECT * FROM boilerplates WHERE tenant_id=? ORDER BY block_name", (tenant_id,))
    return render_template("boilerplate.html", blocks=rows)


@app.route("/t/<int:tenant_id>/blocks/<int:block_id>/delete", methods=["POST"])
def block_delete(tenant_id, block_id):
    d.run("DELETE FROM boilerplates WHERE id=? AND tenant_id=?", (block_id, tenant_id))
    flash("Block deleted.")
    return redirect(url_for("blocks", tenant_id=tenant_id))


# ---------- deadline calendar ----------
@app.route("/t/<int:tenant_id>/calendar")
def calendar(tenant_id):
    opps = with_bands(opportunities(tenant_id, ACTIVE_OPP))
    opps.sort(key=lambda o: (o[1] is None, o[1] if o[1] is not None else 0))
    return render_template("calendar.html", opps=opps)


# ---------- deadline reminders (v2) ----------
@app.route("/t/<int:tenant_id>/reminders")
def reminder_list(tenant_id):
    ensure_reminders(tenant_id)
    rows = d.q(
        """SELECT r.*, o.title AS opp_title, o.funder, o.deadline
           FROM reminders r JOIN opportunities o ON o.id=r.opportunity_id
           WHERE r.tenant_id=? ORDER BY r.read, r.created DESC, r.id DESC""",
        (tenant_id,),
    )
    return render_template("reminders.html", reminders=rows)


@app.route("/t/<int:tenant_id>/reminders/<int:rem_id>/read", methods=["POST"])
def reminder_read(tenant_id, rem_id):
    d.run("UPDATE reminders SET read=1 WHERE id=? AND tenant_id=?", (rem_id, tenant_id))
    return redirect(url_for("reminder_list", tenant_id=tenant_id))


@app.route("/t/<int:tenant_id>/reminders/read-all", methods=["POST"])
def reminder_read_all(tenant_id):
    d.run("UPDATE reminders SET read=1 WHERE tenant_id=?", (tenant_id,))
    flash("All reminders marked read.")
    return redirect(url_for("reminder_list", tenant_id=tenant_id))


# ---------- custom per-funder templates (v2) ----------
def template_sections(tpl_id):
    return d.q("SELECT * FROM app_template_sections WHERE template_id=? ORDER BY position",
               (tpl_id,))


def get_template(tenant_id, tpl_id):
    return d.q1("SELECT * FROM app_templates WHERE id=? AND tenant_id=?", (tpl_id, tenant_id))


@app.route("/t/<int:tenant_id>/templates", methods=["GET", "POST"])
def tpl_list(tenant_id):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Template name is required.")
        else:
            tid = d.run(
                "INSERT INTO app_templates (tenant_id, name, funder, created) VALUES (?,?,?,?)",
                (tenant_id, name, request.form.get("funder", "").strip(),
                 date.today().isoformat()),
            )
            flash("Template saved.")
            return redirect(url_for("tpl_detail", tenant_id=tenant_id, tpl_id=tid))
        return redirect(url_for("tpl_list", tenant_id=tenant_id))
    tpls = d.q("SELECT * FROM app_templates WHERE tenant_id=? ORDER BY name", (tenant_id,))
    return render_template("templates.html", templates=tpls)


@app.route("/t/<int:tenant_id>/templates/<int:tpl_id>", methods=["GET", "POST"])
def tpl_detail(tenant_id, tpl_id):
    tpl = get_template(tenant_id, tpl_id)
    if not tpl:
        flash("Template not found.")
        return redirect(url_for("tpl_list", tenant_id=tenant_id))
    if request.method == "POST":
        if "delete" in request.form:
            d.run("DELETE FROM app_templates WHERE id=?", (tpl_id,))
            flash("Template deleted.")
            return redirect(url_for("tpl_list", tenant_id=tenant_id))
        if "add_section" in request.form:
            pos = d.q1("SELECT COALESCE(MAX(position),-1)+1 p FROM app_template_sections"
                       " WHERE template_id=?", (tpl_id,))["p"]
            d.run(
                "INSERT INTO app_template_sections (template_id, position, heading, prompt, word_target)"
                " VALUES (?,?,?,?,?)",
                (tpl_id, pos, request.form.get("heading", "").strip() or "New section",
                 request.form.get("prompt", "").strip(),
                 int(request.form.get("word_target") or 0)),
            )
            flash("Section added to template.")
            return redirect(url_for("tpl_detail", tenant_id=tenant_id, tpl_id=tpl_id))
    return render_template("template_detail.html", tpl=tpl, sections=template_sections(tpl_id))


@app.route("/t/<int:tenant_id>/templates/<int:tpl_id>/section/<int:sec_id>/delete",
           methods=["POST"])
def tpl_section_delete(tenant_id, tpl_id, sec_id):
    tpl = get_template(tenant_id, tpl_id)
    if not tpl:
        flash("Template not found.")
        return redirect(url_for("tpl_list", tenant_id=tenant_id))
    d.run("DELETE FROM app_template_sections WHERE id=? AND template_id=?", (sec_id, tpl_id))
    flash("Section removed from template.")
    return redirect(url_for("tpl_detail", tenant_id=tenant_id, tpl_id=tpl_id))


def seed_sections_from(app_id, sections):
    """Seed an application's sections from TEMPLATE_SECTIONS tuples or
    template_section rows (both supported)."""
    for i, s in enumerate(sections):
        if isinstance(s, (tuple, list)):
            heading, prompt, target = s
        else:
            heading, prompt, target = s["heading"], s["prompt"], s["word_target"]
        d.run(
            "INSERT INTO app_sections (application_id, position, heading, prompt, word_target)"
            " VALUES (?,?,?,?,?)",
            (app_id, i, heading, prompt or "", target or 0),
        )


# ---------- applications ----------
@app.route("/t/<int:tenant_id>/apps")
def app_list(tenant_id):
    apps = d.q(
        """SELECT a.*, o.title AS opp_title, o.funder, o.deadline,
                  (SELECT COUNT(*) FROM app_sections s WHERE s.application_id=a.id) AS nsec,
                  (SELECT COUNT(*) FROM app_sections s WHERE s.application_id=a.id
                    AND TRIM(s.body) != '') AS ndone
           FROM applications a LEFT JOIN opportunities o ON o.id=a.opportunity_id
           WHERE a.tenant_id=? ORDER BY a.id DESC""",
        (tenant_id,),
    )
    return render_template("applications.html", apps=apps)


@app.route("/t/<int:tenant_id>/apps/new", methods=["GET", "POST"])
def app_new(tenant_id):
    opps = opportunities(tenant_id, ACTIVE_OPP)
    tpls = d.q("SELECT * FROM app_templates WHERE tenant_id=? ORDER BY name", (tenant_id,))
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Title is required.")
            return redirect(url_for("app_new", tenant_id=tenant_id))
        opp_id = request.form.get("opportunity_id") or None
        app_id = d.run(
            "INSERT INTO applications (tenant_id, opportunity_id, title, status, created)"
            " VALUES (?,?,?,?,?)",
            (tenant_id, opp_id, title, "drafting", date.today().isoformat()),
        )
        tpl_id = request.form.get("template_id") or ""
        if tpl_id and get_template(tenant_id, int(tpl_id)):
            seed_sections_from(app_id, template_sections(int(tpl_id)))
            flash("Application started from your template.")
        else:
            seed_sections_from(app_id, TEMPLATE_SECTIONS)
            flash("Application started from template.")
        if opp_id:
            d.run("UPDATE opportunities SET status='drafting' WHERE id=?", (opp_id,))
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    return render_template("app_new.html", opps=opps, templates=tpls)


import hashlib


def _record_grant_commit(tenant_id, app_id, sec_id, heading, author, action_kind, summary, before_body, after_body):
    now_iso = datetime.now().isoformat(timespec="seconds")
    raw = f"{tenant_id}|{app_id}|{sec_id}|{author}|{action_kind}|{before_body}|{after_body}|{now_iso}"
    chash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    d.run(
        """INSERT INTO grant_commits
           (commit_hash, tenant_id, application_id, section_id, section_heading,
            author, action_kind, summary, before_body, after_body, created)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (chash, tenant_id, app_id, sec_id, heading, author or "Coordinator",
         action_kind, summary, before_body, after_body, now_iso),
    )
    return chash


@app.route("/t/<int:tenant_id>/apps/<int:app_id>", methods=["GET", "POST"])
def app_detail(tenant_id, app_id):
    app_row = d.q1(
        """SELECT a.*, o.title AS opp_title, o.funder, o.deadline
           FROM applications a LEFT JOIN opportunities o ON o.id=a.opportunity_id
           WHERE a.id=? AND a.tenant_id=?""",
        (app_id, tenant_id),
    )
    if not app_row:
        flash("Application not found.")
        return redirect(url_for("app_list", tenant_id=tenant_id))
    if request.method == "POST":
        if "delete" in request.form:
            d.run("DELETE FROM applications WHERE id=?", (app_id,))
            flash("Application deleted.")
            return redirect(url_for("app_list", tenant_id=tenant_id))
        if "add_section" in request.form:
            heading = request.form.get("heading", "").strip() or "New section"
            pos = d.q1("SELECT COALESCE(MAX(position),-1)+1 p FROM app_sections WHERE application_id=?",
                       (app_id,))["p"]
            d.run(
                "INSERT INTO app_sections (application_id, position, heading, prompt, word_target)"
                " VALUES (?,?,?,?,?)",
                (app_id, pos, heading, request.form.get("prompt", "").strip(),
                 int(request.form.get("word_target") or 0)),
            )
            flash("Section added.")
            return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
        # section edit
        sec_id = int(request.form["section_id"])
        prev_sec = d.q1("SELECT * FROM app_sections WHERE id=? AND application_id=?", (sec_id, app_id))
        before_body = prev_sec["body"] if prev_sec else ""
        sec_heading = prev_sec["heading"] if prev_sec else "Section"
        body = request.form.get("body", "")
        contributor = request.form.get("contributor", "").strip()
        insert_block = request.form.get("insert_block")
        action_kind = "section_edit"
        if insert_block:
            blk = d.q1("SELECT block_name, body FROM boilerplates WHERE id=? AND tenant_id=?",
                       (insert_block, tenant_id))
            if blk and blk["body"]:
                body = (body + "\n\n" + blk["body"]).strip()
                action_kind = "boilerplate_insert"
                flash("Boilerplate inserted.")
        d.run(
            "UPDATE app_sections SET body=?, contributor=? WHERE id=? AND application_id=?",
            (body, contributor, sec_id, app_id),
        )
        if before_body != body:
            chash = _record_grant_commit(
                tenant_id, app_id, sec_id, sec_heading,
                contributor or (prev_sec["contributor"] if prev_sec else "Coordinator"),
                action_kind,
                f"Edited '{sec_heading}' ({word_count(before_body)} → {word_count(body)} words)",
                before_body, body,
            )
            if not insert_block:
                flash(f"Section saved (commit {chash[:7]}).")
        elif not insert_block:
            flash("Section saved.")
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    sections = d.q("SELECT * FROM app_sections WHERE application_id=? ORDER BY position", (app_id,))
    blocks = d.q("SELECT id, block_name FROM boilerplates WHERE tenant_id=? ORDER BY block_name",
                 (tenant_id,))
    commits = d.q(
        "SELECT * FROM grant_commits WHERE tenant_id=? AND application_id=? ORDER BY id DESC LIMIT 25",
        (tenant_id, app_id),
    )
    enriched = []
    total_words = total_target = done = 0
    for s in sections:
        sd = dict(s)
        wc = word_count(s["body"])
        sd["words"] = wc
        total_words += wc
        total_target += s["word_target"] or 0
        if s["body"].strip():
            done += 1
        enriched.append(sd)
    days, band = (None, "none")
    if app_row["deadline"]:
        days, band = deadline_band({"deadline": app_row["deadline"]})
    return render_template(
        "application.html", app_row=app_row, sections=enriched, blocks=blocks,
        done=done, total=len(sections), total_words=total_words,
        total_target=total_target, days=days, band=band, commits=commits,
    )


@app.route("/t/<int:tenant_id>/apps/<int:app_id>/undo", methods=["POST"])
def app_undo_commit(tenant_id, app_id):
    """One-click Undo for any grant application section edit/import."""
    commit_id = request.form.get("commit_id")
    if commit_id:
        c = d.q1(
            "SELECT * FROM grant_commits WHERE id=? AND tenant_id=? AND application_id=?",
            (int(commit_id), tenant_id, app_id),
        )
    else:
        c = d.q1(
            """SELECT * FROM grant_commits
               WHERE tenant_id=? AND application_id=? AND reverted=0
               ORDER BY id DESC LIMIT 1""",
            (tenant_id, app_id),
        )
    if not c:
        flash("Nothing to undo.")
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    sec = d.q1("SELECT * FROM app_sections WHERE id=? AND application_id=?",
               (c["section_id"], app_id))
    cur_body = sec["body"] if sec else ""
    d.run("UPDATE app_sections SET body=? WHERE id=? AND application_id=?",
          (c["before_body"], c["section_id"], app_id))
    d.run("UPDATE grant_commits SET reverted=1 WHERE id=?", (c["id"],))
    undo_hash = _record_grant_commit(
        tenant_id, app_id, c["section_id"], c["section_heading"],
        "UndoEngine", "revert",
        f"Reverted {c['commit_hash'][:7]} on '{c['section_heading']}'",
        cur_body, c["before_body"],
    )
    d.run("UPDATE grant_commits SET reverted=1 WHERE commit_hash=?", (undo_hash,))
    flash(f"Restored '{c['section_heading']}' to state before commit {c['commit_hash'][:7]}.")
    return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))


@app.route("/t/<int:tenant_id>/apps/<int:app_id>/section/<int:sec_id>/delete", methods=["POST"])
def section_delete(tenant_id, app_id, sec_id):
    d.run("DELETE FROM app_sections WHERE id=? AND application_id=?", (sec_id, app_id))
    flash("Section deleted.")
    return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))


# ---------- draft assist stub (v2) ----------
def draft_assist(tenant_id, section):
    """Assemble a honestly-labeled TEMPLATE STARTER from the section prompt
    plus the tenant's boilerplate library (rule-based, no model involved).

    SEAM FOR REAL AI LATER (see SPEC.md §6): replace this function body with
    a model call. Keep the output honestly labeled — never present generated
    text as human-written or as model-written when it isn't.
    """
    blocks = d.q("SELECT block_name, body FROM boilerplates WHERE tenant_id=? ORDER BY block_name",
                 (tenant_id,))
    mission = next((b["body"] for b in blocks if "mission" in b["block_name"].lower()), "")
    lines = ["[TEMPLATE STARTER — assembled from your boilerplate by a rule, not by AI.",
              " Edit every word before submitting.]", ""]
    if mission:
        lines.append(mission.strip())
        lines.append("")
    lines.append("What this section asks for: %s" % (section["prompt"] or section["heading"]))
    lines.append("Draft %d+ words here that tie your project to the funder's priorities,"
                 " then delete this starter text." % (section["word_target"] or 100))
    return "\n".join(lines)


def get_section(tenant_id, app_id, sec_id):
    return d.q1(
        """SELECT s.* FROM app_sections s JOIN applications a ON a.id=s.application_id
           WHERE s.id=? AND s.application_id=? AND a.tenant_id=?""",
        (sec_id, app_id, tenant_id),
    )


@app.route("/t/<int:tenant_id>/apps/<int:app_id>/section/<int:sec_id>/assist",
           methods=["POST"])
def section_assist(tenant_id, app_id, sec_id):
    sec = get_section(tenant_id, app_id, sec_id)
    if not sec:
        flash("Section not found.")
        return redirect(url_for("app_list", tenant_id=tenant_id))
    starter = draft_assist(tenant_id, sec)
    before_body = sec["body"]
    body = sec["body"].strip()
    new_body = starter if not body else body + "\n\n" + starter
    d.run("UPDATE app_sections SET body=? WHERE id=?", (new_body, sec_id))
    _record_grant_commit(
        tenant_id, app_id, sec_id, sec["heading"], sec["contributor"] or "DraftAssist",
        "draft_assist", f"Inserted template starter into '{sec['heading']}'",
        before_body, new_body,
    )
    flash("Template starter added — edit every word before submitting.")
    return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))


# ---------- budget spreadsheet import (v2) ----------
import csv
import io

CSV_HEADERS = {
    "category": {"category", "cat", "type"},
    "description": {"description", "desc", "item", "details", "detail"},
    "amount": {"amount", "cost", "price", "total", "value"},
}


def normalize_csv_headers(fieldnames):
    """Map a CSV header row onto (category, description, amount); None if
    the amount column is missing (we can't import money without it)."""
    mapping = {}
    for raw in fieldnames or []:
        key = (raw or "").strip().lower()
        for canon, aliases in CSV_HEADERS.items():
            if key in aliases and canon not in mapping:
                mapping[canon] = raw
    return mapping if "amount" in mapping else None


def parse_amount(raw, rowno):
    s = (raw or "").strip().replace("$", "").replace(",", "")
    if not s:
        return None, "Row %d: amount is blank — skipped." % rowno
    try:
        return float(s), None
    except ValueError:
        return None, "Row %d: amount '%s' is not a number — skipped." % (rowno, raw.strip())


def budget_section_for(app_id):
    sec = d.q1(
        "SELECT * FROM app_sections WHERE application_id=? AND LOWER(heading) LIKE '%budget%'"
        " ORDER BY position LIMIT 1",
        (app_id,),
    )
    if sec:
        return sec
    pos = d.q1("SELECT COALESCE(MAX(position),-1)+1 p FROM app_sections WHERE application_id=?",
               (app_id,))["p"]
    sec_id = d.run(
        "INSERT INTO app_sections (application_id, position, heading, prompt, word_target)"
        " VALUES (?,?,?,?,?)",
        (app_id, pos, "Budget",
         "Line items: what the money buys. Tie each line to the project summary.", 150),
    )
    return d.q1("SELECT * FROM app_sections WHERE id=?", (sec_id,))


@app.route("/t/<int:tenant_id>/apps/<int:app_id>/budget/import", methods=["POST"])
def budget_import(tenant_id, app_id):
    app_row = d.q1("SELECT * FROM applications WHERE id=? AND tenant_id=?", (app_id, tenant_id))
    if not app_row:
        flash("Application not found.")
        return redirect(url_for("app_list", tenant_id=tenant_id))
    upload = request.files.get("csv")
    if not upload or not upload.filename:
        flash("Choose a CSV file to import.")
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    try:
        text = upload.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        flash("Could not read the file as text (needs UTF-8 CSV).")
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    reader = csv.DictReader(io.StringIO(text))
    mapping = normalize_csv_headers(reader.fieldnames)
    if not mapping:
        flash("No amount column found — need one of: amount, cost, price, total, value.")
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    items, errors, total = [], [], 0.0
    for i, row in enumerate(reader, start=2):
        cat = (row.get(mapping.get("category", "")) or "").strip() if "category" in mapping else ""
        desc = (row.get(mapping.get("description", "")) or "").strip() if "description" in mapping else ""
        amount, err = parse_amount(row.get(mapping["amount"]), i)
        if err:
            errors.append(err)
            continue
        if not cat and not desc:
            errors.append("Row %d: no category or description — skipped." % i)
            continue
        items.append((cat or "General", desc or "—", amount))
        total += amount
    if not items:
        flash("Nothing imported.")
        for e in errors:
            flash(e)
        return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))
    block = ["Budget line items (imported %s):" % date.today().isoformat()]
    for cat, desc, amount in items:
        block.append("- %s: %s — $%.2f" % (cat, desc, amount))
    block.append("")
    block.append("Total: $%.2f" % total)
    sec = budget_section_for(app_id)
    before_body = sec["body"]
    body = sec["body"].strip()
    new_body = "\n".join(block) if not body else body + "\n\n" + "\n".join(block)
    d.run("UPDATE app_sections SET body=? WHERE id=?", (new_body, sec["id"]))
    _record_grant_commit(
        tenant_id, app_id, sec["id"], sec["heading"], "CSV_Import",
        "budget_import", f"Imported {len(items)} budget line items (${total:.2f})",
        before_body, new_body,
    )
    flash("Imported %d line items ($%.2f total)%s." %
          (len(items), total, "" if not errors else " — %d row(s) skipped, see below" % len(errors)))
    for e in errors:
        flash(e)
    return redirect(url_for("app_detail", tenant_id=tenant_id, app_id=app_id))


@app.route("/t/<int:tenant_id>/apps/<int:app_id>/submit", methods=["POST"])
def app_submit(tenant_id, app_id):
    app_row = d.q1("SELECT * FROM applications WHERE id=? AND tenant_id=?", (app_id, tenant_id))
    if not app_row:
        flash("Application not found.")
        return redirect(url_for("app_list", tenant_id=tenant_id))
    opp = None
    if app_row["opportunity_id"]:
        opp = d.q1("SELECT * FROM opportunities WHERE id=?", (app_row["opportunity_id"],))
    d.run(
        "INSERT INTO submissions (tenant_id, application_id, opportunity_id, title, funder,"
        " submitted_at, outcome) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, app_id, app_row["opportunity_id"], app_row["title"],
         opp["funder"] if opp else "", date.today().isoformat(), "pending"),
    )
    d.run("UPDATE applications SET status='submitted' WHERE id=?", (app_id,))
    if opp:
        d.run("UPDATE opportunities SET status='submitted' WHERE id=?", (opp["id"],))
    flash("Submission logged. Good luck!")
    return redirect(url_for("sub_list", tenant_id=tenant_id))


# ---------- submission log ----------
@app.route("/t/<int:tenant_id>/subs", methods=["GET", "POST"])
def sub_list(tenant_id):
    if request.method == "POST":
        sub_id = int(request.form["sub_id"])
        d.run(
            "UPDATE submissions SET outcome=?, award_amount=?, notes=? WHERE id=? AND tenant_id=?",
            (request.form.get("outcome", "pending"), float(request.form.get("award_amount") or 0),
             request.form.get("notes", "").strip(), sub_id, tenant_id),
        )
        flash("Submission updated.")
        return redirect(url_for("sub_list", tenant_id=tenant_id))
    subs = d.q("SELECT * FROM submissions WHERE tenant_id=? ORDER BY submitted_at DESC, id DESC",
               (tenant_id,))
    totals = d.q1(
        "SELECT COUNT(*) c, COALESCE(SUM(CASE WHEN outcome='won' THEN award_amount ELSE 0 END),0) won"
        " FROM submissions WHERE tenant_id=?",
        (tenant_id,),
    )
    return render_template("submissions.html", subs=subs, totals=totals, outcomes=SUB_OUTCOMES)


# ---------- co-op aggregate (no cross-tenant detail leakage) ----------
@app.route("/coop")
def coop():
    rows = d.q(
        """SELECT t.id, t.name, t.kind,
                  (SELECT COUNT(*) FROM opportunities o WHERE o.tenant_id=t.id
                    AND o.status IN ('researching','drafting')) AS active_opps,
                  (SELECT COUNT(*) FROM applications a WHERE a.tenant_id=t.id
                    AND a.status='drafting') AS drafting,
                  (SELECT COUNT(*) FROM submissions s WHERE s.tenant_id=t.id) AS subs,
                  (SELECT COALESCE(SUM(CASE WHEN s.outcome='won' THEN s.award_amount ELSE 0 END),0)
                    FROM submissions s WHERE s.tenant_id=t.id) AS won_total
           FROM tenants t ORDER BY t.name""",
    )
    totals = d.q1(
        "SELECT COUNT(*) c, COALESCE(SUM(CASE WHEN outcome='won' THEN award_amount ELSE 0 END),0) won"
        " FROM submissions"
    )
    return render_template("coop.html", rows=rows, totals=totals)


if __name__ == "__main__":
    # The Flask dev server is intentionally gone: it must never serve a
    # pilot. The production entrypoint is gunicorn (see Dockerfile):
    #   gunicorn --workers 2 --bind 0.0.0.0:${PORT:-5058} app:app
    raise SystemExit(
        "Refusing to run the Flask dev server. Use gunicorn: "
        "gunicorn --workers 2 --bind 0.0.0.0:${PORT:-5058} app:app"
    )
