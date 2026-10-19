# OBB Grants Module 2 — Spec

## 1. Purpose

Give co-op member organizations (small businesses, community kitchens,
tailors, nonprofits) a shared grant-writing pipeline. Grants are how
small orgs fund the things revenue can't cover — equipment, training,
food — but each org currently reinvents the boilerplate, misses
deadlines, and loses track of what it applied for. One shared backend
fixes all three at once.

## 2. Data model

Dates are ISO strings `YYYY-MM-DD` (`''` = none). Money is REAL (CAD).

- **tenants** — `id, name, kind, contact_note`
- **opportunities** — `id, tenant_id, title, funder, deadline, amount, eligibility_notes, status (researching/drafting/submitted/won/lost), notes`
- **boilerplates** — `id, tenant_id, block_name, body, updated`
- **applications** — `id, tenant_id, opportunity_id (nullable), title, status (drafting/ready/submitted), created`
- **app_sections** — `id, application_id, position, heading, prompt, word_target (0 = none), body, contributor`
- **submissions** — `id, tenant_id, application_id (nullable), opportunity_id (nullable), title, funder, submitted_at, outcome (pending/won/lost), award_amount, notes`

Tenancy: every row carries `tenant_id` (sections inherit it through
their application). The prototype enforces this by query filtering (no
auth); v2 needs real per-tenant credentials. The co-op aggregate queries
select only counts and sums — never titles, funders, bodies, or notes —
so no tenant's details leak into the shared view.

## 3. Deadline engine

For each opportunity with status in (`researching`, `drafting`) and a
parseable deadline:

1. `days = (deadline − today).days`.
2. Band: `days < 0` → `past`; `days ≤ 7` → `urgent`; `days ≤ 30` → `soon`;
   otherwise `ok`; no deadline → `none`.
3. `urgent` and `past` render red (alert banner + `badrow` rows);
   `soon` renders amber.

The engine runs on every dashboard, opportunities, and calendar page
load — no caching in v1. Deliberately flags past-due drafting items:
a missed deadline you haven't noticed is the failure mode this module
exists to kill.

## 4. Application drafting model

- New applications seed from `TEMPLATE_SECTIONS` (5 sections: project
  summary, organizational background, community impact, budget,
  contact), each with a guidance prompt and word target.
- A section is "filled" when its body is non-empty after stripping.
- Progress = filled/total sections + total words vs total word targets.
- **Boilerplate insert**: appending a library block to a section body
  (separated by a blank line) — the one-click reuse loop.
- **Contributors**: free-text name per section, so a team can split work
  visibly without accounts in v1.
- Custom sections (add/delete) supported; position ordering is
  insertion order in v1.

## 5. Submission flow

`POST /apps/<id>/submit` creates a `submissions` row (outcome
`pending`), sets the application to `submitted`, and — if linked —
the opportunity to `submitted`. Outcomes and award amounts are edited
afterward on the submission log page. Deleting an opportunity or
application nulls (not cascades) the linked submission's foreign keys,
so the log survives.

## 6. Stubbed for v2 — now built

- **Custom templates**: `app_templates` + `app_template_sections` tables;
  saved per tenant, seeded into new applications via `seed_sections_from()`.
- **Budget spreadsheet import**: CSV → Budget section line items, per-row
  error reporting, totals validated (`budget_import`, `parse_amount`,
  `normalize_csv_headers` in app.py).
- **AI-assisted drafting**: `draft_assist()` in app.py is the model seam —
  currently a rule-based TEMPLATE STARTER assembled from the section
  prompt + tenant boilerplate, honestly labeled. To plug in a real model:
  replace the body of `draft_assist(tenant_id, section)` with a model
  call that returns starter text; keep the `[TEMPLATE STARTER …]` label
  and the "edit every word" flash so generated text is never presented
  as human-written. Human approves every word before submit.
- **Reminders**: `reminders` table + `ensure_reminders()` (30/7/1-day
  boundaries, overdue, idempotent) + in-app feed with unread badges.

## 7. Stubbed for v3

- **Auth**: per-tenant logins; coordinator vs contributor roles (today
  anyone can edit anything within a tenant; the tenant picker is v1).
- **Hard tenancy**: DB-level or app-level guarantee one tenant can't
  read another's rows (today it's query-filter convention).
- **Funder API integrations**: pull open opportunities from public
  grant databases instead of manual entry.
- **Real AI drafting**: swap the `draft_assist()` seam for a model call
  (labeling discipline above is the contract).
- **Reminder delivery**: wire `NOTIFICATION_SENDERS` in app.py to
  email/SMS (30/7/1-day cadence already generated in-app).
- **Module 1+2 single sign-on**: one login, one tenant picker, both
  modules (scheduling + grants) under it.
