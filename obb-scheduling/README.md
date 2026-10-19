# One Big Backend — Co-op Scheduling, Module 1 (v2)

A multi-tenant weekly staff scheduler for independent cannabis retail shops,
built for Manitoba's Bill 56 (proposed mandatory minimum staffing: no one
works alone during high-risk hours). Each shop manages its own schedule; the
co-op dashboard shows aggregate stats across member shops — the credit-union
view.

v2 adds real logins (manager/staff roles, hard tenant isolation), weekly
availability + time-off requests, one-click copy-week scheduling, and an
in-app notification feed.

## Run it

```bash
cd ~/workspace/obb-scheduling
./venv/bin/python seed.py   # (re)seed demo data
# serve with gunicorn (the Flask dev server was removed on purpose):
./venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5057 app:app
# → http://127.0.0.1:5057
```

Or with your own Python: `pip install -r requirements.txt`, then run as above.

Environment knobs:
- `PORT` — port to serve on (default 5057)
- `OBB_DB` — path to the SQLite file (default `./obb.db`)
- `OBB_SECRET` — session signing key. **Set this in production**
  (`fly secrets set OBB_SECRET=...`); the dev fallback must never serve
  real users.
- `OBB_COOKIE_SECURE` — set to `1` when serving over HTTPS (always on
  Fly.io); makes the session cookie `Secure`.

Tests: `./venv/bin/python tests/test_v2.py` (17 checks, runs against a temp DB).

## Demo logins

Password for every demo account: `demo-pass`

| Shop     | Username  | Role    |
|----------|-----------|---------|
| Big Buds | `marleen` | manager |
| Big Buds | `josh`    | staff   |
| Big Buds | `priya`   | staff   |
| Lucy's   | `lucy`    | manager |
| Lucy's   | `devon`   | staff   |
| Lucy's   | `aisha`   | staff   |

## What's in the demo

Two fictional Winnipeg shops, seeded shifts in week 1:

- **Big Buds** (9am–11pm, $5,000/wk budget) — 5 staff. **Has one intentional
  Bill 56 violation**: Friday 8–11pm has only 1 staffer on the floor where
  the rule requires 2. Also has one pending shift-swap request, one approved
  time-off (Sam, Monday), one pending time-off request (Josh, Friday), and
  two unread manager notifications.
- **Lucy's** (8am–9pm, $5,000/wk budget) — 4 staff, fully compliant week,
  zero violations. The contrast shop.

## Features (v2)

1. **Login** — per-shop usernames + passwords (werkzeug hashes), manager vs
   staff roles. Session-scoped tenancy: any cross-shop URL is a hard 403.
2. **Weekly scheduler** — add/delete shifts per employee per day per week;
   store hours enforced; overlapping shifts for the same employee blocked.
   Week navigator (this week + 7 ahead).
3. **Bill 56 rule engine** — configurable "minimum N staff during window"
   rules (days, time window, on/off). Violations computed in 30-minute
   buckets and shown as red banners on the dashboard, schedule, and rules
   pages.
4. **Labor-cost tracking** — per-employee and per-shop weekly hours × wage;
   flags staff over their max hours/week; budget bar warns at 80% and
   alarms at 100% of the weekly cap (set in Settings).
5. **Shift swaps** — staff can only offer their own shifts; requests are
   overlap-checked; manager approves (reassigns the shift) or denies.
   Approval also blocks if the taker has approved time-off then.
6. **Availability** — staff set weekly recurring available windows; managers
   see everyone's.
7. **Time off** — staff request week-specific time off; managers
   approve/deny. Approved time-off hard-blocks new shifts in that window,
   and the schedule page warns about already-scheduled overlaps.
8. **Copy week** — one click duplicates a full week into the next, skipping
   (and reporting) conflicting shifts.
9. **Notifications** — in-app feed per user: shift assigned/removed, swap
   requested/approved/denied, time-off requested/approved/denied, staffing
   violations (managers, once/day). Email/SMS plugs into
   `NOTIFICATION_SENDERS` in app.py later.
10. **Co-op dashboard** — aggregate totals across member shops (hours, labor
    cost, average cost/shop, violation counts). Staff names never leave
    their shop.

Mobile-friendly layout throughout — owners check schedules on phones.

## Project layout

```
app.py            Flask app: routes + Bill 56 rule engine + auth + notifications
db.py             SQLite schema + helpers (+ additive v2 migration)
seed.py           Demo data (2 shops, logins, availability, time-off)
tests/test_v2.py 17 test-client checks (temp DB)
templates/        Jinja pages (no JS framework, no build step)
static/style.css  Hand-written responsive CSS
SPEC.md           Data model + rule-engine spec
```

## Pilot readiness

This module is containerized and hardened for a pilot deployment.

**Docker** (build from this directory):

```bash
docker build -t obb-scheduling .
docker run -d --name obb-scheduling \
  -p 5057:5057 \
  -e OBB_SECRET="$(openssl rand -hex 32)" \
  -v obb-scheduling-data:/data \
  obb-scheduling
```

`seed.py` starts clean (deletes all rows) — demos only, never against a
live pilot DB.

**Fly.io**: `fly.toml` is in this directory (app `obb-scheduling`,
region `yyz`, internal port 5057, HTTPS forced, 1 GB volume at `/data`).

```bash
fly launch            # rename to obb-scheduling if prompted
fly volumes create obb_scheduling_data --region yyz --size 1
fly secrets set OBB_SECRET="$(openssl rand -hex 32)"   # mandatory
fly deploy
```

**Security checklist** (full detail in `SECURITY.md`):

- Real logins (werkzeug scrypt hashes), manager/staff roles, hard 403s
  on cross-tenant access — 17 adversarial attacks defended, 0 gaps.
- Session cookies: `HttpOnly` + `SameSite=Lax` always, `Secure` on HTTPS.
- No Flask dev server anywhere; gunicorn (2 workers) is the only server.
- No hardcoded secrets; `OBB_SECRET` comes from the environment.
- Known limitations: no rate limiting, no CSRF tokens yet, SQLite
  single-writer, app-level (not DB-level) tenancy. Read `SECURITY.md`
  before a pilot with real data.

## What's stubbed for v3

See SPEC.md §6. Short version: payroll export, LGCA coverage-log export,
DB-level tenancy guarantees, Bayesian demand forecasting, and deeper
Module 1+2 integration.
