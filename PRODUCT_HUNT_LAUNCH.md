# One Big Backend — Product Hunt Launch Kit (`PRODUCT_HUNT_LAUNCH.md`)

## 1. Core Listing Copy

- **Product Name**: One Big Backend
- **Tagline (60 chars max)**: Git-backed undo & co-op operations for small businesses
- **Alternative Taglines**:
  - *The Undo button for small business schedules, grants & inventory*
  - *Member-owned B Corp infrastructure: nothing can plug One Big Backend*
- **Topics / Categories**: `Open Source`, `Productivity`, `Spreadsheets`, `Small Business`, `Git`, `Operations`
- **License**: GNU AGPLv3 (Open Source)

---

## 2. The Maker's First Comment (Copy-Paste Ready for Launch Day)

Hey Product Hunt! 👋

I’m Viv (Christopher Duguay), a grad student, TA (CUPE 3909), and backend builder in Winnipeg.

I started building **One Big Backend** after watching independent shops, parishes, unions, and community orgs in my city drown in software costs and fragile spreadsheets while corporate chains got enterprise infrastructure at a fraction of the per-store cost.

**The chains have backends. The little guys don't. That's the whole game.**

While building our first three operational modules, we realized that the single most underrated primitive in software development—**`git` (content-addressed history, 1-click `undo`, and 3-way structural merges)**—is almost completely missing from everyday small-business tools.

Other business software deletes your mistakes permanently. **One Big Backend lets you take them back.**

### What's in the AGPLv3 Repo Today:

1. **Module 1: Co-op Shift Scheduling + Manitoba Bill 56 Compliance (`obb-scheduling`)**
   - Multi-tenant shift rosters, labor-cost/budget warnings, shift swaps, availability, and a 30-minute bucket rule engine that flags minimum-staffing violations in plain English.
   - **The Stage Demo Moment**: Click `Clear week` to nuke all 27 shifts in a shop's schedule—watch the compliance warnings light up—then click **`↶ Undo last change`** and watch all 27 shifts restore bit-for-bit.
2. **Module 2: Shared Co-op Grant Pipeline (`obb-grants`)**
   - Opportunity tracker, 30/7/1-day deadline reminders, reusable boilerplate library, CSV budget importer, and **Git-backed section revision history with 1-click Undo** so contributors never overwrite each other's grant drafts.
3. **Module 3: Parish & Community Lending Library (`obb-library`)**
   - Built for local community & parish lending libraries (starting with St. Ignatius Spiritual Education Centre): searchable online catalog, 1-click borrower checkout, automatic overdue tracking, and full Git audit/undo history.
4. **Module 4: Universal Semantic Git Engine (`obbe_semantic_git.py`)**
   - Solves the "expensive binary blob" problem for `.xlsx` spreadsheets, `.csv` sheets, and POS `.json` work orders.
   - Performs cell- and field-level **3-Way Merges** and automatically catches **`[FORMULA_CLOBBERED_BY_HARDCODE]`**—alerting you the instant someone overwrites an active Excel formula (`=Stock*UnitCost`) with a hardcoded number.

### Why AGPLv3 + Co-op Ownership?
Small businesses and community organizations shouldn't have their shared infrastructure enclosed by outside SaaS extractors. By licensing under **GNU AGPLv3** and organizing as a member-owned co-op ("a credit union for business infrastructure"), any improvements made to the network service stay open to the members who use it.

We're knocking on doors in Winnipeg and inviting contributors everywhere to help us expand the modules. Try the 60-second local demo, nuke a schedule, hit Undo, and let us know what format or small-business workflow we should git-ify next! 🧦⚙️🧦
