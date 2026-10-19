"""Seed demo data: two fictional co-op members — a tailor shop and a
community kitchen — with boilerplate blocks, grant opportunities,
an in-progress application, and submission history."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
import db as d

app = Flask(__name__)
app.config["DB_PATH"] = os.environ.get(
    "OBB_DB", os.path.join(os.path.dirname(__file__), "obb.db")
)
d.init_db(app)

TODAY = date.today()
iso = lambda dt: dt.isoformat()
D = lambda n: iso(TODAY + timedelta(days=n))  # n days from today

with app.app_context():
    db = d.get_db()
    for t in ("reminders", "app_template_sections", "app_templates",
              "submissions", "app_sections", "applications",
              "boilerplates", "opportunities", "tenants"):
        db.execute(f"DELETE FROM {t}")
    db.commit()

    # ---------- tenant 1: tailor shop ----------
    tailor = d.run(
        "INSERT INTO tenants (name, kind, contact_note) VALUES (?,?,?)",
        ("Academy Road Tailor Co-op", "Tailor shop",
         "Fictional demo tenant — bespoke garments, alterations, apprenticeships"),
    )
    for name, body in [
        ("Mission",
         "Academy Road Tailor Co-op keeps the craft of bespoke tailoring alive in "
         "Winnipeg's River Heights neighbourhood. We make and repair garments to "
         "last decades, not seasons, and we train apprentices — including "
         "newcomers to Canada — in a trade that pays a living wage."),
        ("History",
         "Founded in 2019 by two journeyman tailors, the co-op grew from a "
         "two-machine alteration shop into a five-person worker co-operative. "
         "In 2024 we launched a paid apprenticeship stream; three graduates now "
         "work full-time in the trade."),
        ("Budget summary",
         "Annual operating budget $185,000. Revenue: 70% bespoke and alteration "
         "work, 20% apprenticeship contracts, 10% fabric sales. We seek grant "
         "funding only for training equipment and apprentice stipends — never "
         "for general operations."),
        ("Contact",
         "Academy Road Tailor Co-op, 458 Academy Rd (fictional), Winnipeg MB. "
         "Contact: the shop manager, (204) 555-0148, hello@example.org."),
    ]:
        d.run(
            "INSERT INTO boilerplates (tenant_id, block_name, body, updated)"
            " VALUES (?,?,?,?)",
            (tailor, name, body, iso(TODAY)),
        )

    opp_apprentice = d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (tailor, "Trades Apprenticeship Equipment Grant", "Manitoba Trades Fund (fictional)",
         D(5), 25000.0,
         "Registered Manitoba businesses with an active apprenticeship program; "
         "equipment must remain in-province 3 years.", "drafting"),
    )
    d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (tailor, "Neighbourhood Arts & Craft Grant", "Winnipeg Arts Council (fictional)",
         D(20), 8000.0,
         "Craft-based nonprofits and co-ops; projects must include a public exhibition.",
         "researching"),
    )
    d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (tailor, "Heritage Trades Preservation Fund", "Canadian Heritage (fictional)",
         D(75), 40000.0,
         "Organizations preserving traditional trades; matching funds required.",
         "researching"),
    )

    # in-progress application on the urgent opportunity
    from app import TEMPLATE_SECTIONS
    app1 = d.run(
        "INSERT INTO applications (tenant_id, opportunity_id, title, status, created)"
        " VALUES (?,?,?,?,?)",
        (tailor, opp_apprentice, "Apprenticeship equipment 2026", "drafting", iso(TODAY)),
    )
    filled = {
        "Project summary": ("We will buy two industrial sewing machines and a steam press so "
                            "our apprenticeship stream can take six trainees instead of three. "
                            "Graduates leave with a journeyman-track portfolio.", "A. Tailor"),
        "Organizational background": ("Founded 2019; five-person worker co-op; three apprenticeship "
                                      "graduates now employed full-time in the trade.", "A. Tailor"),
    }
    for i, (heading, prompt, target) in enumerate(TEMPLATE_SECTIONS):
        body, contrib = filled.get(heading, ("", ""))
        d.run(
            "INSERT INTO app_sections (application_id, position, heading, prompt, word_target, body, contributor)"
            " VALUES (?,?,?,?,?,?,?)",
            (app1, i, heading, prompt, target, body, contrib),
        )

    # past submission: won
    d.run(
        "INSERT INTO submissions (tenant_id, application_id, title, funder, submitted_at,"
        " outcome, award_amount, notes) VALUES (?,?,?,?,?,?,?,?)",
        (tailor, None, "Shop accessibility retrofit", "City Community Grant (fictional)",
         D(-120), "won", 12000.0, "Wheelchair ramp and widened fitting room; completed on budget."),
    )

    # demo per-funder template for the tailor shop
    trades_tpl = d.run(
        "INSERT INTO app_templates (tenant_id, name, funder, created) VALUES (?,?,?,?)",
        (tailor, "Trades Fund template", "Manitoba Trades Fund (fictional)", iso(TODAY)),
    )
    for i, (heading, prompt, target) in enumerate([
        ("Apprenticeship plan", "How many trainees, over what period, supervised by whom?", 150),
        ("Equipment list", "Each item, its cost, and why the training needs it.", 100),
        ("Employer letters", "Which employers will hire graduates? Attach letters.", 50),
    ]):
        d.run(
            "INSERT INTO app_template_sections (template_id, position, heading, prompt, word_target)"
            " VALUES (?,?,?,?,?)",
            (trades_tpl, i, heading, prompt, target),
        )

    # ---------- tenant 2: community kitchen ----------
    kitchen = d.run(
        "INSERT INTO tenants (name, kind, contact_note) VALUES (?,?,?)",
        ("North End Community Kitchen", "Community kitchen",
         "Fictional demo tenant — free weekday lunches, cooking classes"),
    )
    for name, body in [
        ("Mission",
         "Nobody in the North End goes hungry. We serve a free hot lunch every "
         "weekday, run community cooking classes, and buy produce from Manitoba "
         "family farms whenever we can."),
        ("History",
         "Started in 2016 as a church-basement soup pot. Now an independent "
         "nonprofit serving 400 lunches a week with a crew of 12 volunteers "
         "and 2 part-time coordinators."),
        ("Budget summary",
         "Annual budget $96,000: 55% food, 25% coordinator wages, 20% rent and "
         "utilities. Every grant dollar goes to food and wages; admin is "
         "covered by monthly donors."),
        ("Contact",
         "North End Community Kitchen, 123 Selkirk Ave (fictional), Winnipeg MB. "
         "Contact: the coordinator, (204) 555-0173, kitchen@example.org."),
    ]:
        d.run(
            "INSERT INTO boilerplates (tenant_id, block_name, body, updated)"
            " VALUES (?,?,?,?)",
            (kitchen, name, body, iso(TODAY)),
        )

    d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (kitchen, "Emergency Food Security Fund", "Manitoba Food Grants (fictional)",
         D(12), 30000.0,
         "Registered nonprofits serving food-insecure households; quarterly reporting required.",
         "researching"),
    )
    opp_fridge = d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (kitchen, "Community Fridge Expansion", "Healthy Neighbourhoods (fictional)",
         D(45), 15000.0,
         "Capital projects expanding free food access points.", "researching"),
    )
    # overdue drafting opportunity -> shows "past" warning
    d.run(
        "INSERT INTO opportunities (tenant_id, title, funder, deadline, amount,"
        " eligibility_notes, status) VALUES (?,?,?,?,?,?,?)",
        (kitchen, "Winter Warmth Meals", "Seasonal Giving Circle (fictional)",
         D(-9), 5000.0, "Holiday-season meal programs.", "drafting"),
    )

    app2 = d.run(
        "INSERT INTO applications (tenant_id, opportunity_id, title, status, created)"
        " VALUES (?,?,?,?,?)",
        (kitchen, opp_fridge, "Second community fridge", "drafting", iso(TODAY)),
    )
    for i, (heading, prompt, target) in enumerate(TEMPLATE_SECTIONS):
        d.run(
            "INSERT INTO app_sections (application_id, position, heading, prompt, word_target)"
            " VALUES (?,?,?,?,?)",
            (app2, i, heading, prompt, target),
        )

    # pending submission
    d.run(
        "INSERT INTO submissions (tenant_id, application_id, title, funder, submitted_at,"
        " outcome, notes) VALUES (?,?,?,?,?,?,?)",
        (kitchen, None, "Summer lunch program top-up", "City Community Grant (fictional)",
         D(-30), "pending", "Decision expected next month."),
    )

print("Seeded 2 tenants (tailor shop, community kitchen) with boilerplates,")
print("opportunities, in-progress applications, and submission history.")
