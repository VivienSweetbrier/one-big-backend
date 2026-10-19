"""Seed demo data: two fictional Winnipeg shops, staff, a week of shifts,
Bill 56 staffing rules, one pending swap request, logins, availability,
time-off requests, and a few notifications."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from werkzeug.security import generate_password_hash
import db as d

app = Flask(__name__)
app.config["DB_PATH"] = os.environ.get(
    "OBB_DB", os.path.join(os.path.dirname(__file__), "obb.db")
)
d.init_db(app)

with app.app_context():
    db = d.get_db()
    # start clean
    for t in ("schedule_commits", "notifications", "time_off", "availability", "users",
              "swap_requests", "staffing_rules", "shifts", "employees", "shops"):
        db.execute(f"DELETE FROM {t}")
    db.commit()

    H = lambda h, m=0: h * 60 + m  # hours -> minutes

    # ---------- shop 1: Big Buds ----------
    big = d.run(
        "INSERT INTO shops (name, open_minutes, close_minutes, weekly_budget, address_note)"
        " VALUES (?,?,?,?,?)",
        ("Big Buds", H(9), H(23), 5000.0, "Demo shop — Ness Ave corridor"),
    )
    big_emp = {}
    for name, role, wage, maxh in [
        ("Marleen", "Manager", 24.00, 48),
        ("Josh", "Budtender", 18.00, 56),
        ("Priya", "Budtender", 17.50, 64),
        ("Sam", "Cashier", 16.50, 32),
        ("Rae", "Budtender", 17.00, 48),
    ]:
        big_emp[name] = d.run(
            "INSERT INTO employees (shop_id, name, role, hourly_wage, max_hours_week)"
            " VALUES (?,?,?,?,?)",
            (big, name, role, wage, maxh),
        )

    def shift(shop, empdict, emp, day, s, e):
        d.run(
            "INSERT INTO shifts (shop_id, employee_id, day, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?)",
            (shop, empdict[emp], day, H(*s), H(*e)),
        )
    B = lambda emp, day, s, e: shift(big, big_emp, emp, day, s, e)

    # Mon–Thu: 2-person cover through close
    for day in (0, 1, 2, 3):
        B("Marleen", day, (9,), (17,))
        B("Josh", day, (9,), (17,))
        B("Priya", day, (13,), (23,))
        B("Rae", day, (17,), (23,))
    # Fri: INTENTIONAL VIOLATION — only Josh on floor 8pm–11pm
    B("Marleen", 4, (9,), (17,))
    B("Josh", 4, (9,), (23,))
    B("Priya", 4, (9,), (17,))
    B("Sam", 4, (12,), (20,))
    # Sat: full cover
    B("Marleen", 5, (9,), (15,))
    B("Josh", 5, (9,), (17,))
    B("Priya", 5, (11,), (23,))
    B("Sam", 5, (15,), (23,))
    B("Rae", 5, (9,), (15,))
    # Sun: Rae + Sam close together
    B("Rae", 6, (10,), (23,))
    B("Sam", 6, (10,), (23,))

    d.run(
        """INSERT INTO staffing_rules
           (shop_id, name, min_staff, days, start_minutes, end_minutes, active)
           VALUES (?,?,?,?,?,?,1)""",
        (big, "Bill 56 — high-risk hours (8pm–close)", 2, "0,1,2,3,4,5,6", H(20), H(23)),
    )

    # one pending swap: Sam wants Marleen to take his Saturday evening
    sam_sat = d.q1(
        "SELECT id FROM shifts WHERE shop_id=? AND employee_id=? AND day=5",
        (big, big_emp["Sam"]),
    )
    d.run(
        """INSERT INTO swap_requests
           (shop_id, shift_id, from_employee_id, to_employee_id, note, status, created)
           VALUES (?,?,?,?,?, 'pending', '2026-10-13T14:00:00')""",
        (big, sam_sat["id"], big_emp["Sam"], big_emp["Marleen"],
         "Family dinner — can you cover my Saturday close?"),
    )

    # ---------- shop 2: Lucy's ----------
    luc = d.run(
        "INSERT INTO shops (name, open_minutes, close_minutes, weekly_budget, address_note)"
        " VALUES (?,?,?,?,?)",
        ("Lucy's", H(8), H(21), 5000.0, "Demo shop — munchie market"),
    )
    luc_emp = {}
    for name, role, wage, maxh in [
        ("Lucy", "Owner", 26.00, 44),
        ("Devon", "Budtender", 18.00, 60),
        ("Aisha", "Budtender", 17.00, 64),
        ("Theo", "Budtender", 17.00, 56),
    ]:
        luc_emp[name] = d.run(
            "INSERT INTO employees (shop_id, name, role, hourly_wage, max_hours_week)"
            " VALUES (?,?,?,?,?)",
            (luc, name, role, wage, maxh),
        )

    L = lambda emp, day, s, e: shift(luc, luc_emp, emp, day, s, e)

    # Mon–Fri: 2-person cover through the 8pm–9pm high-risk window
    for day in (0, 1, 2, 3, 4):
        L("Lucy", day, (8,), (16,))
        L("Devon", day, (10,), (18,))
        L("Aisha", day, (12,), (21,))
        L("Theo", day, (16,), (21,))
    # Sat–Sun: Theo + Aisha close together
    for day in (5, 6):
        L("Devon", day, (8,), (16,))
        L("Theo", day, (8,), (21,))
        L("Aisha", day, (12,), (21,))

    d.run(
        """INSERT INTO staffing_rules
           (shop_id, name, min_staff, days, start_minutes, end_minutes, active)
           VALUES (?,?,?,?,?,?,1)""",
        (luc, "Bill 56 — high-risk hours (8pm–close)", 2, "0,1,2,3,4,5,6", H(20), H(21)),
    )

    # ---------- v2: logins ----------
    pw = generate_password_hash("demo-pass")
    users = {}
    for username, shop, empdict, emp, role in [
        ("marleen", big, big_emp, "Marleen", "manager"),
        ("josh", big, big_emp, "Josh", "staff"),
        ("priya", big, big_emp, "Priya", "staff"),
        ("lucy", luc, luc_emp, "Lucy", "manager"),
        ("devon", luc, luc_emp, "Devon", "staff"),
        ("aisha", luc, luc_emp, "Aisha", "staff"),
    ]:
        users[username] = d.run(
            "INSERT INTO users (shop_id, employee_id, username, password_hash, role)"
            " VALUES (?,?,?,?,?)",
            (shop, empdict[emp], username, pw, role),
        )

    # ---------- v2: availability (weekly recurring) ----------
    for emp, day, s, e in [
        (big_emp["Josh"], 0, (9,), (17,)),
        (big_emp["Josh"], 5, (9,), (17,)),
        (luc_emp["Devon"], 0, (8,), (16,)),
    ]:
        d.run(
            "INSERT INTO availability (shop_id, employee_id, day, start_minutes, end_minutes)"
            " VALUES (?,?,?,?,?)",
            (big if emp in big_emp.values() else luc, emp, day, H(*s), H(*e)),
        )

    # ---------- v2: time off ----------
    # Sam: approved Monday 9–5 (he has no Monday shift — clean demo of the block)
    d.run(
        """INSERT INTO time_off
           (shop_id, employee_id, week, day, start_minutes, end_minutes,
            reason, status, created)
           VALUES (?,?,0,1,?,?,?,'approved','2026-10-14T09:00:00')""",
        (big, big_emp["Sam"], H(9), H(17), "Dentist appointment"),
    )
    # Josh: pending Friday 12–4 (overlaps his shift — shows the request flow)
    d.run(
        """INSERT INTO time_off
           (shop_id, employee_id, week, day, start_minutes, end_minutes,
            reason, status, created)
           VALUES (?,?,0,4,?,?,?,'pending','2026-10-14T10:30:00')""",
        (big, big_emp["Josh"], H(12), H(16), "Concert tickets"),
    )

    # ---------- v2: notifications ----------
    d.run(
        """INSERT INTO notifications
           (shop_id, user_id, kind, text, link, created, read)
           VALUES (?,?,?,?,?,?,0)""",
        (big, users["marleen"], "swap_requested",
         "Swap requested: Sam's Saturday shift (3:00 PM–11:00 PM) needs approval.",
         f"/shop/{big}/swaps", "2026-10-13T14:00:01"),
    )
    d.run(
        """INSERT INTO notifications
           (shop_id, user_id, kind, text, link, created, read)
           VALUES (?,?,?,?,?,?,0)""",
        (big, users["marleen"], "coverage_violation",
         "1 staffing violation(s) in week 1 (first: Fri 8:00 PM–11:00 PM, "
         "needs 2, has 1).",
         f"/shop/{big}/schedule?week=0", "2026-10-14T08:00:00"),
    )

    print("Seeded 2 shops (Big Buds, Lucy's) with staff, shifts, rules, 1 swap request,")
    print("6 logins (password: demo-pass), availability, time-off, and 2 notifications.")
