# SECURITY.md — OBB Module 2 (grants)

Pilot-readiness security notes. This is a prototype hardening pass, not a
full audit. Read before putting real organizational data behind this.

## Tenancy isolation — how it's enforced, and where

- Every row carries `tenant_id` (opportunities, boilerplates,
  applications, submissions, reminders, app_templates; app_sections
  inherit it through their application).
- `load_tenant()` (`app.py`, `@app.before_request`) resolves the URL's
  `tenant_id` → tenant row; unknown tenants redirect home. All list/detail
  queries filter on `tenant_id`.
- The co-op aggregate (`/coop`) selects **only counts and sums** — never
  titles, funder names, bodies, notes, or reminder text — so no tenant's
  details leak into the shared view (probed by test G6/G6b).
- ⚠️ **Module 2 v2 has no authentication.** The tenant picker is trust-me:
  anyone who can reach the app can open any tenant's URLs (recorded as
  known gaps G1/G2 below). Tenancy is a query-filter convention, not a
  guarantee. **Real per-tenant auth is the top v3 item** (SPEC.md §7) and
  must land before any pilot with real data.

## Authentication

- None yet in v2 (see above). Session cookie flags (`HttpOnly`,
  `SameSite=Lax`, `Secure` when `OBB_COOKIE_SECURE=1`) are configured for
  the flash-message session and the v3 auth to come.

## What the dev-server removal changed

- `app.py` no longer calls `app.run()` — `python app.py` now **refuses**
  with instructions to use gunicorn.
- DB schema creation moved to **import time** (`d.init_db(app)` at module
  level, idempotent) so gunicorn workers boot against initialized tables.
- `get_db()` connections use `timeout=30` so the two gunicorn workers
  wait on SQLite's write lock instead of failing fast.

## Known limitations

- **No authentication / authorization** (see above) — the headline gap.
- **No rate limiting.**
- **SQLite concurrency** — one writer at a time; fine for a pilot.
- **No CSRF tokens** — POSTs rely on `SameSite=Lax` only.
- **OBB_SECRET fallback** — dev key if unset; `fly secrets set OBB_SECRET`
  is mandatory in production.
- **CSV import** — amounts must be plain numbers; formula-like values
  (`=1+1`) are rejected as non-numeric (tested G5). Uploads are parsed as
  text only, never executed.

## Adversarial test results

`tests/test_adversarial.py` — run 2026-10-15. 6 defended, **2 known gaps**
(the gaps are the missing auth, already on the v3 roadmap):

| # | Attack | Expected | Result |
|---|--------|----------|--------|
| G1 | Cross-tenant read (`/t/<B>/` with no login) | blocked | **GAP — attack succeeds (no auth in v2)** |
| G2 | Cross-tenant write (POST opportunity into tenant B) | blocked | **GAP — attack succeeds (no auth in v2)** |
| G3 | Stored SQL injection in opportunity title | table intact, stored literally | PASS |
| G4 | SQL injection via URL id (`/opps/1 OR 1=1`) | 404, no query run | PASS |
| G5/G5b | CSV formula injection (`=1+1` amount) | rejected; valid rows still import | PASS |
| G6/G6b | Co-op aggregate probing for tenant B title/funder | absent from `/coop` | PASS |

Task-based pilot flow (`tests/test_pilot_flow.py`): 6 steps —
create opportunity → draft application from template (opp flips to
drafting) → import budget CSV ($6,100.00 total) → log submission
(app + opp flip to submitted) — **all pass** with no human help.
