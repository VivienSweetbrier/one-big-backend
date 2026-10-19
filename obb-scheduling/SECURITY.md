# SECURITY.md — OBB Module 1 (scheduling)

Pilot-readiness security notes. This is a prototype hardening pass, not a
full audit. Read before putting real shop data behind this.

## Tenancy isolation — how it's enforced, and where

- Every row carries `shop_id` (shops, employees, users, shifts,
  staffing_rules, swap_requests, availability, time_off, notifications).
- `load_user()` (`app.py`, `@app.before_request`) resolves the session's
  `user_id` → user row, and **clears the session** if the user no longer
  exists or the session's `shop_id` doesn't match the user's row.
- `guard(shop_id)` runs on every `/shop/<id>` route: unauthenticated →
  redirect to login; `g.shop.id != URL shop_id` → **HTTP 403**
  (`templates/403.html`).
- `manager_only()` gates all management routes (schedule edits, roster,
  rules, settings, copy-week, approvals): staff role → 403, in both
  routes and templates.
- Staff can only offer **their own** shifts for swap (`own_employee()`).

This is an **app-level** guarantee. There is no database-level row
security; anyone with the SQLite file sees everything. v3 roadmap:
per-shop DB files or row-level security.

## Authentication

- Passwords hashed with **werkzeug `generate_password_hash`**
  (scrypt, the werkzeug default; per-password salts). Verified with
  `check_password_hash` on login. No plaintext anywhere.
- Sessions are Flask signed cookies (itsdangerous, keyed by `OBB_SECRET`).
- Post-login `next` redirect is validated: only same-host paths
  (`/…`, never `//…` or absolute URLs) — no open redirect.
- Session cookie flags: `HttpOnly`, `SameSite=Lax` always;
  `Secure` when `OBB_COOKIE_SECURE=1` (set in Dockerfile/fly.toml —
  always on HTTPS deployments).

## What the dev-server removal changed

- `app.py` no longer calls `app.run()` — `python app.py` now **refuses**
  with instructions to use gunicorn. The debug reloader, debugger PIN,
  and single-threaded dev socket are gone from every serving path.
- DB schema creation moved to **import time** (`d.init_db(app)` at module
  level, idempotent) so gunicorn workers — which never run `__main__` —
  boot against initialized tables.
- `db._migrate()` was made safe for concurrent worker boot (two workers
  racing the `ALTER TABLE` no longer crash; the loser rolls back).
- `get_db()` connections use `timeout=30` so the two gunicorn workers
  wait on SQLite's write lock instead of failing fast.

## Known limitations

- **No rate limiting** — login endpoint has no throttling or lockout.
  Put this behind a WAF / Fly's edge protections for a real pilot.
- **SQLite concurrency** — one writer at a time; fine for a pilot
  (tens of users), not for high write throughput.
- **No CSRF tokens** — state-changing POSTs rely on `SameSite=Lax` +
  session auth only. Add Flask-WTF CSRF before handling sensitive data.
- **OBB_SECRET fallback** — if unset, the app uses a dev key and every
  deployment shares it (sessions forgeable). `fly secrets set OBB_SECRET`
  is mandatory; fly.toml documents this.
- **Session invalidation** — sessions live until cookie expiry; no
  server-side revocation list (password change doesn't kill old sessions).
- **App-level tenancy only** (see above).

## Adversarial test results

`tests/test_adversarial.py` — 17 attacks, **all defended** (run 2026-10-15):

| # | Attack | Expected | Result |
|---|--------|----------|--------|
| A1/A1b | Tenant A staff GETs tenant B dashboard/schedule | 403 | PASS |
| A2 | Tenant A staff POSTs shift into tenant B | 403 | PASS |
| A3/A3b/A3c | Staff POSTs manager-only shift add / GETs settings / POSTs time-off approval | 403 | PASS |
| A4/A4b | Tampered session cookie | rejected, redirect to login | PASS |
| A5/A5b/A5c | SQL injection at login (`' OR '1'='1`) | rejected, no session, users table intact | PASS |
| A6 | Stored SQL injection via shop settings name | table intact, stored literally | PASS |
| A7 | Unauthenticated direct `/shop/1` access | redirect to login | PASS |
| A8/A8b | Open redirect via `next=https://evil…` / `//evil…` | forced to same-host path | PASS |
| A9/A9b | Session cookie flags | HttpOnly + SameSite present | PASS |

Task-based pilot flow (`tests/test_pilot_flow.py`): 7 steps —
manager login → assign shift → staff time-off request → manager approval
→ approved time-off blocks conflicting shift → copy-week — **all pass**
with no human help.
