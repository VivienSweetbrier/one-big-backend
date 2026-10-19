# One Big Backend (`one-big-backend`)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

> **"The chains have backends. The little guys don't. That's the whole game."**
>
> **One Big Backend** is member-owned, co-op business infrastructure for independent shops, unions, parishes, credit unions, and community organizations in Winnipeg and Manitoba. Built for B Corp certification — transparent governance, zero vendor lock-in, and protected under **GNU AGPLv3** so corporate chains can never enclose the co-op's plumbing.
>
> *"Nothing can plug One Big Backend."*

---

## What's Inside

| Module | Directory | Port | Purpose |
| :--- | :--- | :--- | :--- |
| **Module 1: Co-op Shift Scheduling & Bill 56 Guard** | [`obb-scheduling/`](./obb-scheduling) | `5057` | Multi-tenant shift scheduling, 30-minute Manitoba Bill 56 minimum-staffing violation engine, labor-cost & budget warnings, shift swaps, availability, time-off approvals, **and V3 1-Click Git Undo (`History / Undo`)**. |
| **Module 2: Co-op Grant Pipeline** | [`obb-grants/`](./obb-grants) | `5058` | Multi-tenant opportunity tracker, 30/7/1-day deadline reminders, shared boilerplate library, collaborative application drafter, CSV budget importer, **and V3 Section Revision Git History + 1-Click Undo**. |
| **Module 3: Parish & Community Lending Library** | [`obb-library/`](./obb-library) | `5059` | Searchable online catalog, quick borrower checkout/return, automatic overdue detection, **and 1-Click Git Undo** (built initially for the St. Ignatius Spiritual Education Centre Lending Library & Holy Rosary bilingual shelf). |
| **Module 4: Universal Semantic Git Engine** | [`obbe_semantic_git.py`](./obbe_semantic_git.py) | CLI / Lib | Format-specific 3-way structural merge & formula-clobber guard for spreadsheets (`.xlsx`/`.csv`), POS/dispatch `.json`, and SQLite tables. |
| **Module 5: The Universal Undo Button (Freemium Web SaaS)** | [`obb-undo/`](./obb-undo) | `5060` | Self-serve **Freemium** web app (`Tier 0: Community Free Forever` -> `Tier 1: Co-op Pro Merge-Guard` -> `Tier 2: Multi-Site Patron`) giving spreadsheets and business tables 1-Click Time-Travel Undo and Formula-Clobber shields. |
| **Module 6: Bayesian $M/G/c$ Queue & Demand Verifier** | [`bayesian_queue.py`](./bayesian_queue.py) | Integrated in `5057` | Integrates [`VivienSweetbrier/bayesian-queue`](https://github.com/VivienSweetbrier/bayesian-queue): models non-memoryless, heavy-tailed Weibull ($k < 1$) service times and Poisson arrivals to compute posterior traffic intensity $\rho = \frac{\lambda}{c \cdot \mu}$, flag saturation risk $P(\rho \ge 1.0)$, and provide **1-Click Bayesian Auto-Staffing** (`⚡ Auto-staff to c*`). |

---

## The Killer Feature: "The Undo Button" (Git-Backed Business Operations)

Other business software deletes your mistakes permanently; **One Big Backend** lets you take them back.

Every operational mutation across Scheduling, Grants, and Library — adding or deleting a shift, clearing a week's schedule, editing a grant section, importing a budget CSV, or checking out a book — is recorded as a **SHA-256 content-addressed commit** with author, timestamp, and full before/after state:

- **The Stage Demo Moment**: Log into `obb-scheduling` as a manager (`marleen` / `demo-pass`), open **Schedule**, click **`Clear week`** (watching the entire week drop to 0 shifts and Bill 56 alerts light up), and click **`↶ Undo last change`**. All 27 shifts snap back instantaneously.
- **Spreadsheet Formula-Clobber Protection (`obbe_semantic_git.py`)**: Detects when one employee updates inventory counts while another accidentally overwrites an Excel formula (`=Stock*UnitCost`) with a hardcoded number—auto-merging safe columns while isolating the formula collision for human approval.

---

## Quickstart (Run Locally in 60 Seconds)

Requirements: Python 3.10+ and `flask` (`pip install flask gunicorn`).

### 1. Run the Complete Verification Suite (All 55+ Checks)
```bash
python test_v3_undo_and_library.py
python obb-scheduling/tests/test_v2.py
python obb-grants/tests/test_v2.py
python obbe_semantic_git.py
```

### 2. Launch Module 1 — Shift Scheduling (`obb-scheduling`, Port 5057)
```bash
cd obb-scheduling
python seed.py
gunicorn --workers 2 --bind 0.0.0.0:5057 app:app
# Or on Windows for local dev inspection:
python -c "import app; app.app.run(port=5057)"
```
- **Demo Logins** (password `demo-pass`):
  - **Big Buds**: `marleen` (manager), `josh` (staff), `priya` (staff)
  - **Lucy's**: `lucy` (manager), `devon` (staff), `aisha` (staff)

### 3. Launch Module 2 — Grant Pipeline (`obb-grants`, Port 5058)
```bash
cd obb-grants
python seed.py
python -c "import app; app.app.run(port=5058)"
```

### 4. Launch Module 3 — Parish & Community Lending Library (`obb-library`, Port 5059)
```bash
cd obb-library
python -c "import app; app.app.run(port=5059)"
```

---

## Roadmap & Where Contributors Can Jump In

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for details on how to grab an issue and help out:

1. **Unified Single Sign-On (SSO)**: One login & tenant switcher across Scheduling, Grants, and Library.
2. **Module 2 Auth & RBAC**: Bring `obb-scheduling`'s session-scoped manager/staff RBAC into `obb-grants` (coordinator vs. contributor roles).
3. **Database-Level Tenancy Hardening**: Per-tenant SQLite files or PostgreSQL Row-Level Security (RLS) beyond app-level 403 guards.
4. **Email / SMS Notification Fan-Out**: Wire the `NOTIFICATION_SENDERS` seam in `obb-scheduling/app.py` and `obb-grants/app.py` to Twilio / SMTP.
5. **Payroll & LGCA Compliance Exports**: One-click CSV payroll export (`hours × wage`) and Manitoba Bill 56 LGCA coverage audit PDF/CSV export.

---

## License

Copyright (C) 2026 Christopher Duguay (Viv) & One Big Backend Contributors.

This program is free software: you can redistribute it and/or modify it under the terms of the **GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version**. See [`LICENSE`](./LICENSE) for the full text.
