# One Big Backend — Grant-Writing Automation, Module 2 (prototype)

A multi-tenant grant pipeline for co-op member organizations: track grant
opportunities, keep a reusable boilerplate library, get deadline warnings,
draft applications collaboratively from a template, log submissions and
outcomes, and see co-op-wide totals on an aggregate dashboard — the
credit-union view. No tenant ever sees another tenant's grants, drafts,
or submissions.

## Run it

```bash
cd ~/workspace/obb-grants
./venv/bin/python seed.py   # (re)seed demo data: tailor shop + community kitchen
# serve with gunicorn (the Flask dev server was removed on purpose):
./venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5058 app:app
# → http://127.0.0.1:5058
```

Or with your own Python: `pip install -r requirements.txt`, then run as above.

Environment knobs:
- `PORT` — port to serve on (default 5058)
- `OBB_DB` — path to the SQLite file (default `./obb.db`)
- `OBB_SECRET` — session signing key. **Set this in production**
  (`fly secrets set OBB_SECRET=...`); the dev fallback must never serve
  real users.
- `OBB_COOKIE_SECURE` — set to `1` when serving over HTTPS (always on
  Fly.io); makes the session cookie `Secure`.

## What's in the demo

Two fictional Winnipeg co-op members:

- **Academy Road Tailor Co-op** — 4 boilerplate blocks (mission, history,
  budget summary, contact), 3 opportunities (one due in 5 days — flagged
  urgent/red), an in-progress application with 2 of 5 sections filled,
  a saved "Trades Fund template" (custom 3-section per-funder template),
  and one past submission marked won ($12,000).
- **North End Community Kitchen** — 4 boilerplate blocks, 3 opportunities
  including one whose deadline already passed (flagged red), a blank
  templated application, and one pending submission.

## Features (v1)

1. **Tenant picker** — no login in the prototype; pick an organization on
   the home page. Every row carries `tenant_id`; all queries filter on it.
2. **Opportunity tracker** — title, funder, deadline, amount, eligibility
   notes, status (researching/drafting/submitted/won/lost).
3. **Deadline engine** — ≤7 days or passed = red, ≤30 days = amber, shown on
   the dashboard, opportunities list, and a dedicated calendar page.
4. **Boilerplate library** — reusable org-profile blocks; insert any block
   into any application section with one click.
5. **Application drafter** — starts from a 5-section template (project
   summary, background, community impact, budget, contact) with prompts
   and word targets. Multiple contributors fill sections (name recorded
   per section); progress tracked as sections-filled and words-vs-target.
   Custom sections can be added or deleted.
6. **Submission log** — one click logs a submission from an application
   (flips app + opportunity to "submitted"); outcomes (pending/won/lost)
   and award amounts editable afterward.
7. **Co-op dashboard** — per-member counts and total dollars awarded;
   no cross-tenant detail leaks (no opportunity titles, drafts, or
   funder names from other tenants).

## Features (v2)

8. **Deadline reminders** — in-app reminder feed per tenant: generated at
   30/7/1 days before a deadline and when one passes, idempotent (no
   duplicate unread reminders), unread badge in the nav, mark-read /
   mark-all-read. `NOTIFICATION_SENDERS` in app.py is the clean seam for
   email/SMS delivery later.
9. **Budget spreadsheet import** — CSV upload per application
   (category, description, amount columns; aliases accepted) parses line
   items into the Budget section (created if missing), totals them, and
   reports bad rows one by one — valid rows still import.
10. **Draft assist stub** — per-section "Draft assist" button inserts a
    clearly-labeled TEMPLATE STARTER assembled by rule from the section
    prompt + the tenant's boilerplate. Honestly labeled, never presented
    as AI or human writing; `draft_assist()` in app.py is the swap point
    for a real model (see SPEC.md §6).
11. **Custom per-funder templates** — save a named section set (headings,
    prompts, word targets) once per funder; start new applications from
    it via the template picker on the new-application page.

Mobile-friendly layout throughout — coordinators check deadlines on phones.

## Project layout

```
app.py            Flask app: routes + deadline-warning engine
db.py             SQLite schema + helpers
seed.py           Demo data (2 tenants)
templates/        Jinja pages (no JS framework, no build step)
static/style.css  Hand-written responsive CSS (shared with Module 1)
SPEC.md           Data model + engine spec
```

## Pilot readiness

This module is containerized and hardened for a pilot deployment.

**Docker** (build from this directory):

```bash
docker build -t obb-grants .
docker run -d --name obb-grants \
  -p 5058:5058 \
  -e OBB_SECRET="$(openssl rand -hex 32)" \
  -v obb-grants-data:/data \
  obb-grants
```

`seed.py` starts clean (deletes all rows) — demos only, never against a
live pilot DB.

**Fly.io**: `fly.toml` is in this directory (app `obb-grants`, region
`yyz`, internal port 5058, HTTPS forced, 1 GB volume at `/data`).

```bash
fly launch            # rename to obb-grants if prompted
fly volumes create obb_grants_data --region yyz --size 1
fly secrets set OBB_SECRET="$(openssl rand -hex 32)"   # mandatory
fly deploy
```

**Security checklist** (full detail in `SECURITY.md`):

- ⚠️ **No authentication yet** — the tenant picker is trust-me. Real
  per-tenant auth is the top v3 item and must land before any pilot
  with real data. Adversarial tests: 6 attacks defended, 2 known gaps
  (cross-tenant read/write with no login — both the missing auth).
- Co-op aggregate leaks nothing (counts/sums only — probed and verified).
- SQL injection blocked everywhere (parameterized queries; CSV
  formula-like values rejected).
- Session cookies: `HttpOnly` + `SameSite=Lax` always, `Secure` on HTTPS.
- No Flask dev server anywhere; gunicorn (2 workers) is the only server.
- No hardcoded secrets; `OBB_SECRET` comes from the environment.
- Known limitations: no rate limiting, no CSRF tokens yet, SQLite
  single-writer. Read `SECURITY.md` before a pilot with real data.

## What's stubbed for v3

See SPEC.md §6. Short version: real per-tenant auth (roles, hard tenant
isolation), funder API integrations, real AI-assisted drafting (the
`draft_assist()` seam is ready), actual email/SMS reminder delivery (the
`NOTIFICATION_SENDERS` seam is ready), and combined Module 1+2 single
sign-on.
