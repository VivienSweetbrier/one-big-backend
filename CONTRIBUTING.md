# Contributing to One Big Backend

Welcome! We're building shared, member-owned backend infrastructure for Winnipeg's independent small businesses, unions, parishes, and co-ops.

## Design Philosophy

1. **Boring, Auditable Stack**: Python 3 + Flask + SQLite (WAL/timeout-hardened for gunicorn workers) + server-rendered HTML/CSS. Zero bloated JS build steps required to fix a bug.
2. **Event-Sourced Reversibility ("The Undo Button")**: Every destructive or mutating action should record a commit in the module's `*_commits` table so users can undo mistakes with a single click.
3. **Strict Tenant Isolation**: Every query and route must scope strictly to the active `shop_id` / `tenant_id` / `library_id`. Co-op aggregate views (`/coop`) must only expose counts and sums—never individual names, notes, or private tenant records.
4. **Tests Run as Plain Python Scripts**: Each module includes fast, zero-dependency verification scripts in `tests/` (`test_pilot_flow.py`, `test_adversarial.py`, `test_v2.py`) plus the root `test_v3_undo_and_library.py`.

## High-Impact Tasks You Can Grab Right Now

- **[Grants Auth]** Port the `users` table + `@login_required` / `guard()` session scoping from `obb-scheduling/app.py` into `obb-grants/app.py` (closing the #1 item in `obb-grants/SECURITY.md`).
- **[CSRF Tokens]** Add lightweight per-session CSRF token validation across all `POST` forms in `obb-scheduling`, `obb-grants`, and `obb-library`.
- **[Bill 56 & Payroll CSV Exports]** Add `/shop/<id>/export/payroll.csv` and `/shop/<id>/export/bill56-compliance.csv` to `obb-scheduling`.
- **[Library CSV Importer & Barcode Scan]** Add bulk CSV book import (reusing `obb-grants`'s `normalize_csv_headers` pattern) to `obb-library` so parish volunteers can upload existing Excel book lists in one click.
- **[Excel `.xlsx` Upload UI for `obbe_semantic_git.py`]** Wrap `FormatSpecificNormalizer.from_xlsx_bytes` and `SemanticGitEngine.three_way_merge` in a web view so two managers can drag-and-drop conflicting spreadsheets and resolve `[FORMULA_CLOBBERED_BY_HARDCODE]` alerts visually.

## Running Tests Before Opening a PR

```bash
python test_v3_undo_and_library.py
python obb-scheduling/tests/test_v2.py
python obb-scheduling/tests/test_adversarial.py
python obb-grants/tests/test_v2.py
python obb-grants/tests/test_adversarial.py
python obbe_semantic_git.py
```

By contributing to this repository, you agree that your contributions will be licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0-or-later)**.
