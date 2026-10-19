# OBB Scheduling Module 1 — Spec (v2)

## 1. Purpose

Give independent cannabis retail shops a shared, member-owned scheduling
tool that makes Manitoba's Bill 56 minimum-staffing requirement
*impossible to violate by accident*. The scheduler doesn't just record
shifts — it checks them against the law and warns in plain English.

## 2. Data model

All times are integer **minutes since midnight** (e.g. 8pm = 1200).
Days are 0=Mon … 6=Sun. Weeks are 0=this week … 7 (horizon: this week + 7).

- **shops** — `id, name, open_minutes, close_minutes, weekly_budget, address_note`
  - `weekly_budget = 0` disables budget warnings.
- **employees** — `id, shop_id, name, role, hourly_wage, max_hours_week`
- **users** — `id, shop_id, employee_id (nullable), username (unique),
  password_hash (werkzeug), role ('manager'/'staff')`
  - Session stores `user_id` + `shop_id`; every shop route asserts the
    session shop matches the URL shop, else HTTP 403.
- **shifts** — `id, shop_id, employee_id, day, week, start_minutes, end_minutes`
  - Same-day only (`end > start`). Must sit inside store hours.
  - No two shifts for one employee may overlap **within the same week**
    (checked on insert and on swap request/approval).
  - Approved time-off for the same employee/week/day/window blocks insert.
- **staffing_rules** — `id, shop_id, name, min_staff, days (csv), start_minutes, end_minutes, active`
  - Example: "Bill 56 — high-risk hours (8pm–close)", min 2, all days, 1200–1380.
- **swap_requests** — `id, shop_id, shift_id, from_employee_id, to_employee_id, note, status (pending/approved/denied), created`
  - Approving a request reassigns `shifts.employee_id`. Staff may only
    offer their own shifts. Approval re-checks overlap *and* time-off.
- **availability** — `id, shop_id, employee_id, day, start_minutes, end_minutes`
  - Weekly recurring "can work" windows. Staff manage their own;
    managers see everyone's.
- **time_off** — `id, shop_id, employee_id, week, day, start_minutes, end_minutes, reason, status (pending/approved/denied), created`
  - Approved rows block scheduling (hard block on insert) and surface as
    warnings on the schedule page when pre-existing shifts overlap.
- **notifications** — `id, shop_id, user_id, kind, text, link, created, read`
  - In-app feed. Kinds: `shift_assigned`, `swap_requested`,
    `swap_approved`, `swap_denied`, `timeoff_requested`,
    `timeoff_approved`, `timeoff_denied`, `coverage_violation`
    (managers, at most one unread per day).
  - `NOTIFICATION_SENDERS` in app.py is the seam: register
    `fn(user_row, kind, text, link)` callables to fan out to email/SMS.

Tenancy: every row carries `shop_id`. v2 enforces it with session-based
scoping + 403 on mismatch (app-level guarantee; DB-level hardening is v3).

## 3. Bill 56 rule engine

For each shop, for each **active** rule, for each day in the rule's day
list:

1. Build **coverage**: for every 30-minute bucket inside store hours,
   count staff on floor (a shift covers a bucket if
   `shift.start < bucket_end and shift.end > bucket_start`).
2. Flag buckets where `bucket_start` falls inside the rule window
   (`rule.start <= bucket < rule.end`) **and** coverage < `min_staff`.
3. Merge contiguous flagged buckets into violation segments, reporting
   the segment's minimum coverage as `actual`.

Output per violation: `{rule_name, day, start, end, required, actual}`.

Complexity is trivial (buckets ≈ 32/day); the engine runs on every
dashboard/schedule/rules page load — no caching in v1.

**Design note:** the engine flags *any* understaffed window, including
"shop is open but nobody scheduled" (actual = 0). That's intentional:
an uncovered open hour is exactly what Bill 56 is about.

## 4. Labor-cost model

- Per employee: `hours = Σ(end − start)/60`, `cost = hours × hourly_wage`.
- Per shop: sums across staff for the week.
- **Max-hours flag**: employee row highlighted when `hours > max_hours_week`.
- **Budget**: `pct = cost / weekly_budget`; `warn` at ≥80%, `over` at ≥100%.

## 5. Shift swaps

Request = (shift, from-employee, to-employee, note). Overlap-checked at
request time *and* re-checked at approval time (schedules change).
Approval is a single UPDATE reassigning the shift; denial just flips
status. Deleting a shift auto-denies its pending requests.

## 6. v2 — built ✓ / remaining

Built in v2 (October 2026):

- **Auth**: per-shop logins (werkzeug password hashes); manager vs staff
  roles; session-based tenant scoping with hard 403 on cross-shop access.
  Staff can only offer their own shifts for swap; all management routes
  (schedule edits, roster, rules, settings, approvals) are manager-only.
- **Recurring schedules**: multi-week model (week 0–7) + one-click
  copy-week with conflict skipping/reporting.
- **Notifications**: in-app per-user feed (shift assigned/removed, swap
  requested/approved/denied, time-off requested/approved/denied,
  coverage violations). `NOTIFICATION_SENDERS` seam for email/SMS later.
- **Time-off requests** and **availability preferences**: staff submit,
  managers approve/deny; approved time-off hard-blocks scheduling and
  warns on the schedule page.

Still stubbed for v3:

- **Payroll export**: CSV of hours × wage per pay period.
- **Hard tenancy**: DB-level guarantees (row-level security / per-shop
  DB files) beyond the current app-level 403 scoping.
- **Compliance reporting**: export a "Bill 56 coverage log" for LGCA.
- **Demand forecasting**: integrate Christopher's Bayesian queueing work
  for predicted-optimal staffing.
- **Module 1+2 integration**: single sign-on across scheduling and grants.
