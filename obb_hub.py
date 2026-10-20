"""One Big Backend — Master Walk-In Demo Switchboard & Multi-Module Launcher (`obb_hub.py`, Port 5050).

Run one command before leaving the house for Winnipeg walk-ins and appointments:
    python obb_hub.py

Automatically seeds and starts all 5 One Big Backend web modules in the background:
- :5057 -> Module 1 & 6: Shift Scheduling, Bill 56 Guard & Bayesian M/G/c Rush Forecaster
- :5058 -> Module 2: Co-op & Union Grant Pipeline + Section Revision Git Undo
- :5059 -> Module 3: St. Ignatius (925 Jessie Ave) & St. Paul's College Lending Library + Bit-Rot Embed
- :5060 -> Module 5: The Universal Undo Button (Freemium Web SaaS)
- :5061 -> Module 7: K-8 Child Threat-Recognition & Zero-PII Cybersafety Floor

And serves the unified Walk-In Persona Switchboard on http://127.0.0.1:5050.
"""
import os
import subprocess
import sys
import time
from flask import Flask, render_template_string

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = os.environ.get("OBB_SECRET", "obb-prototype-dev-key")


@app.after_request
def apply_security_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'self'"
    return response

def get_modules_for_host(host: str):
    is_public = "sweetbrier.lol" in (host or "").lower()
    u_sched = "https://scheduling.sweetbrier.lol" if is_public else "http://127.0.0.1:5057"
    u_grant = "https://grants.sweetbrier.lol" if is_public else "http://127.0.0.1:5058"
    u_lib   = "https://library.sweetbrier.lol" if is_public else "http://127.0.0.1:5059"
    u_undo  = "https://undo.sweetbrier.lol" if is_public else "http://127.0.0.1:5060"
    u_safe  = "https://safety.sweetbrier.lol" if is_public else "http://127.0.0.1:5061"

    return [
        {
            "id": "jesuit-parish",
            "badge": "⛪ JESUIT & PARISH CORRIDOR (library.sweetbrier.lol)",
            "title": "St. Ignatius Spiritual Library (925 Jessie Ave) & St. Paul's College (U of M)",
            "who": "Carmela Castellano Sinclair (204-453-9243) · Fr. Frank Obrigewitsch, SJ · Rector Chris Adams & Dr. Daniel MacLeod (70 Dysart Rd) · Holy Rosary",
            "pitch": "\"Software should work a little more like Catholic Grace and a little less like Calvinism.\" Rescues stignatius.ca/education-centre/ from legacy CMS HTTP 500 bit-rot with a single-file SQLite catalog and 1-Click Git Undo.",
            "links": [
                ("Open St. Ignatius Library (925 Jessie Ave)", f"{u_lib}/lib/1"),
                ("Open stignatius.ca Bit-Rot Rescue Embed", f"{u_lib}/lib/1/embed"),
                ("Open St. Paul's College (U of M) Shelf", f"{u_lib}/lib/3"),
                ("Open Holy Rosary Bilingual Shelf", f"{u_lib}/lib/2"),
            ],
        },
        {
            "id": "schools-safety",
            "badge": "🛡️ CATHOLIC & PUBLIC SCHOOLS (safety.sweetbrier.lol)",
            "title": "K–8 Child Threat-Recognition & Zero-PII Cybersafety Floor",
            "who": "Manitoba Catholic Schools (Supt. Bob Praznik, St. Ignatius, Christ the King, St. Emile, Holy Ghost) · Men's Group · All 6 Winnipeg Public School Divisions",
            "pitch": "Splits the difference with 100% parent-auditable behavioural threat recognition (Safe Surprises vs. Unsafe Secrets, Spotting Manipulation, Gaming/Chat Traps) + Parent Dinner-Table Scripts. Zero student PII (bypasses FIPPA/PIPEDA PIA bottlenecks).",
            "links": [
                ("Open Manitoba Catholic Schools Floor", f"{u_safe}/board/1"),
                ("Open Winnipeg Public Divisions Floor", f"{u_safe}/board/2"),
                ("Inspect FIPPA / PIPEDA / Safe-Environment Shield", f"{u_safe}/compliance"),
            ],
        },
        {
            "id": "shops-scheduling",
            "badge": "🏪 INDEPENDENT SHOPS, BREWERIES & DISPENSARIES (scheduling.sweetbrier.lol)",
            "title": "Co-op Shift Scheduler, Manitoba Bill 56 Guard & Bayesian M/G/c Forecaster",
            "who": "Big Buds · Lucy's · Chronic Canada · Patent 5 · Nonsuch · Little Brown Jug · Kilter · Good Neighbour (Demo Login: marleen / demo-pass)",
            "pitch": "The 10-second walk-in closer: log in as Marleen, click 'Clear week' (watch all 27 shifts vanish and Bill 56 alarms light up), then hit '↶ Undo last change' to snap all 27 shifts back. Plus 1-Click Bayesian Rush Auto-Staffing.",
            "links": [
                ("Open Big Buds Schedule (Nuke & Undo Demo)", f"{u_sched}/shop/1/schedule"),
                ("Open Bayesian M/G/c Rush Forecaster (c* Auto-Staff)", f"{u_sched}/shop/1/forecast"),
                ("Open Schedule Git Commit History", f"{u_sched}/shop/1/history"),
            ],
        },
        {
            "id": "freemium-undo",
            "badge": "↶ FREEMIUM SAAS FOR EVERY SMALL BUSINESS (undo.sweetbrier.lol)",
            "title": "The Universal Undo Button (Tier 0 Free Forever → Tier 1 Co-op Pro)",
            "who": "Portage Ave Tailor · Farmers' Market Vendors · Parish Treasurers · Credit Union Small-Biz Members",
            "pitch": "Detects when someone accidentally overwrites an Excel formula (=Qty*UnitCost) with a hardcoded number or deletes a row, and restores the exact prior state in one click.",
            "links": [
                ("Open Portage Ave Tailor Clobbered-Formula Demo", f"{u_undo}/ds/1"),
                ("Open St. Ignatius Parish Hall Booking Demo", f"{u_undo}/ds/2"),
                ("View Freemium Co-op Pricing Tiers", f"{u_undo}/pricing"),
            ],
        },
        {
            "id": "grants-pipeline",
            "badge": "📋 CO-OPS, UNIONS & NON-PROFITS (grants.sweetbrier.lol)",
            "title": "Co-op Grant Pipeline, Shared Boilerplates & Section Revision Undo",
            "who": "CUPE 3909 (U of M TAs) · Assiniboine Credit Union · Red River Co-op · Harvest Manitoba · Parish Councils",
            "pitch": "Shared grant deadline radar (30/7/1-day alerts), reusable co-op boilerplate paragraphs, CSV budget importer, and 1-Click Git Undo on every application section.",
            "links": [
                ("Open Tailor Shop Grant Pipeline", f"{u_grant}/t/1/opps"),
                ("Open Collaborative Grant Drafter + 1-Click Undo", f"{u_grant}/t/1/apps/1"),
            ],
        },
    ]


MODULES = get_modules_for_host("127.0.0.1")

HUB_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>One Big Backend · Winnipeg Walk-In Demo Switchboard</title>
<style>
  :root { --bg:#faf8f5; --ink:#1d232a; --muted:#5a6570; --line:#d8d4cc; --accent:#1b4332; --gold:#9a6700; }
  body { font-family: system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--ink); margin:0; line-height:1.5; }
  .topbar { background:var(--accent); color:#fff; padding:1rem 1.6rem; display:flex; justify-content:space-between; align-items:center; }
  .wrap { max-width:1100px; margin:1.5rem auto; padding:0 1rem; }
  .card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:1.25rem; margin-bottom:1.1rem; box-shadow:0 1px 3px rgba(0,0,0,.03); }
  .badge { display:inline-block; background:#d8f3dc; color:#1b4332; font-weight:700; font-size:.78rem; padding:.2rem .6rem; border-radius:5px; }
  .btn-row { display:flex; flex-wrap:wrap; gap:.6rem; margin-top:.85rem; }
  .btn { background:var(--accent); color:#fff; text-decoration:none; padding:.5rem .95rem; border-radius:6px; font-weight:600; font-size:.88rem; display:inline-block; }
  .btn.alt { background:#2d6a4f; }
  .quote-box { background:#fff9db; border-left:4px solid #f59f00; padding:.75rem 1rem; margin-bottom:1.4rem; border-radius:6px; font-size:.95rem; }
</style>
</head>
<body>
<header class="topbar">
  <div>
    <strong style="font-size:1.15rem">🧦⚙️🧦 One Big Backend — Winnipeg Walk-In Demo Switchboard</strong>
    <a href="/blast" style="color:#fff;margin-left:1.2rem;background:#2d6a4f;padding:.35rem .75rem;border-radius:5px;text-decoration:none;font-weight:700;font-size:.86rem">🍵 Open Sick-Day 1-Click Email Blast Console →</a>
  </div>
  <div style="font-size:.86rem">onebigbackend.sweetbrier.lol · GNU AGPLv3 · Member-Owned Co-op Infrastructure</div>
</header>
<main class="wrap">
  <div class="quote-box">
    <strong>💡 Quick Walk-In Opener:</strong>
    <em>"The chains have backends; the little guys don't. I built a Universal Undo Button and shared co-op infrastructure for Winnipeg parishes, schools, and independent shops—because software should work a little more like Catholic Grace and a little less like Calvinism."</em>
  </div>
  {% for m in modules %}
  <div class="card">
    <span class="badge">{{ m.badge }}</span>
    <h2 style="margin:.4rem 0">{{ m.title }}</h2>
    <p style="margin:.2rem 0;font-size:.88rem;color:var(--muted)"><strong>Target Walk-Ins:</strong> {{ m.who }}</p>
    <p style="margin:.5rem 0">{{ m.pitch }}</p>
    <div class="btn-row">
      {% for label, url in m.links %}
      <a class="btn {{ 'alt' if loop.index > 1 else '' }}" href="{{ url }}" target="_blank">{{ label }} →</a>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</main>
</body>
</html>
"""


EMAIL_BLASTS = [
    {
        "wave": "Wave 1 (Send Now — 8:15–9:00 AM): Jesuit & Parish Corridor",
        "name": "St. Ignatius Spiritual Education Centre & Parish (925 Jessie Ave / 255 Stafford St)",
        "phone": "Carmela: 204-453-9243 | Parish Office: 204-474-2351",
        "to": "adult.education@stignatius.ca,office@stignatius.ca",
        "subject": "Your Spiritual Education Centre lending library, online (working prototype ready)",
        "body": (
            "Hi Carmela, Fr. Frank, and the St. Ignatius Parish team,\n\n"
            "I'm Christopher (Viv) — a parishioner who has been to St. Ignatius, a Winnipeg Catholic, and a U of M grad student/TA. "
            "I heard the Spiritual Education Centre's lending library at 925 Jessie Ave needed help getting online (and noticed stignatius.ca/education-centre/ is currently throwing a 500 server error), so I went ahead and built a working prototype for St. Ignatius!\n\n"
            "You can click through the live St. Ignatius Spiritual Library prototype right now:\n"
            "• Live St. Ignatius Catalog & Checkout Tracker: https://library.sweetbrier.lol/lib/1\n"
            "• Drop-In Bit-Rot-Proof Widget for stignatius.ca: https://library.sweetbrier.lol/lib/1/embed\n"
            "• Open-Source Code (GNU AGPLv3): https://github.com/VivienSweetbrier/one-big-backend\n\n"
            "It's part of One Big Backend — shared, parish-owned infrastructure with a 1-Click Undo Button on every checkout and edit (because software should work a little more like Catholic Grace and a little less like Calvinism).\n\n"
            "I'm staying home with a cold today so I don't pass germs around the parish office, but I'd love to book a 15-minute in-person visit at 925 Jessie Ave next week to show you how it works. Does next Tuesday at 10:30 AM or Thursday at 2:00 PM work?\n\n"
            "In Christ,\nViv\nChristopher Duguay"
        ),
    },
    {
        "wave": "Wave 1 (Send Now — 8:15–9:00 AM): Jesuit & Parish Corridor",
        "name": "St. Paul's College at U of M (70 Dysart Rd — Rector Dr. Chris Adams & Dr. Daniel MacLeod)",
        "phone": "204-474-8575",
        "to": "stpauls@umanitoba.ca",
        "subject": "A U of M grad student & TA's Ignatian co-op project (One Big Backend)",
        "body": (
            "Dear Dr. Adams, Dr. MacLeod, and the St. Paul's College community,\n\n"
            "I'm Christopher Duguay — a Catholic grad student and TA right here at the University of Manitoba (and member of CUPE 3909).\n\n"
            "I'm building One Big Backend: an open-source (GNU AGPLv3), member-owned infrastructure suite applying Catholic Social Teaching (Subsidiarity & Solidarity) to real Winnipeg parishes, schools, and small co-ops. We just launched working prototypes for:\n"
            "1. The St. Ignatius Spiritual Education Centre Library & St. Paul's College Seminar Shelf: https://library.sweetbrier.lol/lib/3\n"
            "2. A 100% Parent-Auditable, Zero-PII K–8 Child Threat-Recognition & Safe Environment Floor: https://safety.sweetbrier.lol/board/1\n"
            "3. Full Switchboard & Open-Source Repo: https://onebigbackend.sweetbrier.lol | https://github.com/VivienSweetbrier/one-big-backend\n\n"
            "Every module is built around a cryptographic 'Universal Undo Button' — because software should work a little more like Catholic Grace and a little less like Calvinism.\n\n"
            "I'm recovering from a cold at home today, so I'm writing to see if I could book a 15-minute in-person visit at 70 Dysart Rd next Tuesday or Thursday to share the project with you?\n\n"
            "In Christ,\nChristopher Duguay (Viv)\nUniversity of Manitoba"
        ),
    },
    {
        "wave": "Wave 1 (Send Now — 8:15–9:00 AM): Catholic Schools & Safety Floor",
        "name": "Manitoba Catholic Schools & Principals (Supt. Bob Praznik, St. Ignatius, Christ the King, St. Emile, Holy Ghost)",
        "phone": "MCS Supt: 204-452-2227 | St. Ignatius School: 204-475-1386 | Christ the King: 204-257-0027",
        "to": "rpraznik@archwinnipeg.ca,office@stignatius.mb.ca,office@ctkschool.ca,office@stemileschool.ca,info@holyghostschool.ca",
        "subject": "Zero-PII K-8 Child Threat-Recognition Floor + School Volunteer Scheduler (Winnipeg Catholic Prototype)",
        "body": (
            "Dear Principal / Superintendent,\n\n"
            "I'm Christopher Duguay — a Winnipeg Catholic grad student, U of M TA, and parishioner. Together with a brother from my Catholic men's group, we built a working prototype to solve two urgent needs for our Catholic schools:\n\n"
            "1. A 100% Parent- & Pastor-Auditable K–8 Child Threat-Recognition Floor (https://safety.sweetbrier.lol/board/1):\n"
            "   Teaches practical, age-appropriate behavioural threat recognition (Safe Surprises vs. Unsafe Secrets in K–2, Spotting Manipulation & Isolation in 3–5, and Gaming/Chat Red Flags in 5–8) paired with Parent Dinner-Table Scripts. It stores ZERO bytes of student PII (no student logins, no tracking cookies, strict script-src 'none' CSP), bypassing FIPPA/PIPEDA privacy bottlenecks while locking every word behind a SHA-256 Git seal and 1-Click Undo.\n"
            "2. Shared School & Parish Volunteer Scheduling + Grant Pipeline (https://onebigbackend.sweetbrier.lol):\n"
            "   Open-source (GNU AGPLv3: https://github.com/VivienSweetbrier/one-big-backend) so schools and parishes co-own the plumbing with zero vendor lock-in.\n\n"
            "I'm staying home with a cold today so I don't bring germs into the school office, but I would love to book a 15-minute in-person appointment next week to show you the live prototype on my laptop. Would next Tuesday at 10:00 AM or Thursday at 1:30 PM work for a quick visit?\n\n"
            "In Christ,\nChristopher Duguay (Viv)"
        ),
    },
    {
        "wave": "Wave 2 (Send at 10:30 AM): Independent Shops & Dispensaries",
        "name": "Big Buds Cannabis (3025 Ness Ave Unit J, Sturgeon Creek)",
        "phone": "(431) 441-2837",
        "to": "bigbudscontact@gmail.com",
        "subject": "A trade for the corner of Ness and Sturgeon (working prototype inside)",
        "body": (
            "Hi — I'm Christopher Duguay (Viv), a Winnipeg grad student who builds websites and backend systems for small shops. I'd like to propose a straight trade: I build you backend infrastructure — shared inventory and procurement tooling, online ordering, scheduling help — and we barter for product. No cash changes hands.\n\n"
            "Here's why I'm writing to you specifically: you're the Sturgeon Creek locals — your family grew up here, 25 years building businesses on service-first, and your reviewers keep saying the same thing: lowest prices, good deals, hard-to-find classics, printed menus and all. That price edge is exactly what the MBLL's wholesale markup hike (11% to 13% this June) eats alive. The chains you compete with have corporate buying power. You don't, yet.\n\n"
            "I actually seeded Big Buds into a live working prototype so you can try the 1-Click Schedule Undo and Bayesian Rush Forecaster right now:\n"
            "• Live Prototype (Demo login: marleen / demo-pass): https://scheduling.sweetbrier.lol/shop/1/schedule\n"
            "• Free Forever Spreadsheet Undo Button: https://undo.sweetbrier.lol/ds/1\n"
            "• Open-Source Repo (GNU AGPLv3): https://github.com/VivienSweetbrier/one-big-backend\n\n"
            "I'm home with a cold today so I didn't want to walk into the shop sick, but could I drop by 3025 Ness Ave for 10 minutes next Tuesday or Thursday to show you in person?\n\n"
            "— Viv"
        ),
    },
    {
        "wave": "Wave 3 (Send at 7:15 PM Tonight): Public School Division Trustees",
        "name": "Winnipeg Public School Trustees (WSD, RETSD, LRSD, Pembina Trails, Seven Oaks, St. James-Assiniboia)",
        "phone": "WSD Board Office: 204-775-0231 | LRSD: 204-257-7827",
        "to": "board@wsd1.org,trustees@retsd.mb.ca,communications@lrsd.net,board@pembinatrails.ca,info@7oaks.org,trustees@sjasd.ca",
        "subject": "Splitting the difference on K-8 Child Threat Recognition (100% Parent-Auditable, Zero-Student-PII Floor)",
        "body": (
            "Dear School Trustees,\n\n"
            "I'm Christopher Duguay — a Winnipeg graduate student and TA at the University of Manitoba.\n\n"
            "Regardless of whether families come from traditional/faith-based or progressive backgrounds, every parent in Winnipeg agrees that elementary and middle-school kids urgently need a practical 'public floor' of learned social skills to spot behavioural threats, grooming, manipulation, and unsafe secrets.\n\n"
            "To bridge that divide with 100% transparency, we built an open-source, Zero-Student-PII K–8 Child Threat-Recognition & Cybersafety Floor:\n"
            "• Live Public Division Prototype: https://safety.sweetbrier.lol/board/2\n"
            "• FIPPA / PIPEDA Zero-Student-PII Compliance Architecture: https://safety.sweetbrier.lol/compliance\n"
            "• Open-Source Code (GNU AGPLv3): https://github.com/VivienSweetbrier/one-big-backend\n\n"
            "Because it collects 0 bytes of student PII (no student accounts, no tracking cookies, strict script-src 'none' CSP) and locks every word in a public SHA-256 Git audit log with 1-Click Undo, parents and trustees can verify 100% of what is taught.\n\n"
            "I'd love to book a 15-minute coffee or office appointment next week to walk you through the prototype in person. Does next Tuesday or Thursday work?\n\n"
            "Sincerely,\nChristopher Duguay (Viv)\nUniversity of Manitoba"
        ),
    },
]


@app.route("/")
def index():
    from flask import request
    return render_template_string(HUB_HTML, modules=get_modules_for_host(request.host))


@app.route("/blast")
def email_blast_console():
    import urllib.parse
    cards = []
    for item in EMAIL_BLASTS:
        gmail_url = (
            "https://mail.google.com/mail/?view=cm&fs=1"
            f"&to={urllib.parse.quote(item['to'])}"
            f"&su={urllib.parse.quote(item['subject'])}"
            f"&body={urllib.parse.quote(item['body'])}"
        )
        mailto_url = (
            f"mailto:{item['to']}"
            f"?subject={urllib.parse.quote(item['subject'])}"
            f"&body={urllib.parse.quote(item['body'])}"
        )
        cards.append(
            f"<div class='card'>"
            f"<span class='badge'>{item['wave']}</span>"
            f"<h2 style='margin:.4rem 0'>{item['name']}</h2>"
            f"<p style='margin:.2rem 0;font-size:.88rem;color:var(--muted)'><strong>To:</strong> <code>{item['to']}</code> · <strong>Phone (for 45-sec call):</strong> <code>{item['phone']}</code></p>"
            f"<p style='margin:.4rem 0'><strong>Subject:</strong> {item['subject']}</p>"
            f"<textarea rows='7' style='width:100%;font-family:monospace;font-size:.84rem;padding:.5rem;border:1px solid #d8d4cc;border-radius:6px' readonly>{item['body']}</textarea>"
            f"<div class='btn-row'>"
            f"<a class='btn' href='{gmail_url}' target='_blank'>✉️ 1-Click Open in Gmail Compose →</a>"
            f"<a class='btn alt' href='{mailto_url}'>📬 Open in Default Mail App →</a>"
            f"</div></div>"
        )
    page = HUB_HTML.replace("{{ m.badge }}", "").split("{% for m in modules %}")[0] + "".join(cards) + "</main></body></html>"
    return page


def start_all_subservices():
    """Seeds and spawns all 5 One Big Backend modules as child processes."""
    procs = []
    # Seed Module 1 & Module 2 if needed
    for folder in ("obb-scheduling", "obb-grants"):
        seed_script = os.path.join(ROOT_DIR, folder, "seed.py")
        subprocess.run([sys.executable, seed_script], cwd=os.path.join(ROOT_DIR, folder), check=False)

    service_specs = [
        ("obb-scheduling", 5057),
        ("obb-grants", 5058),
        ("obb-library", 5059),
        ("obb-undo", 5060),
        ("obb-safety-floor", 5061),
    ]
    for folder, port in service_specs:
        cwd = os.path.join(ROOT_DIR, folder)
        cmd = [sys.executable, "-c", f"import app; app.app.run(host='127.0.0.1', port={port}, use_reloader=False)"]
        p = subprocess.Popen(cmd, cwd=cwd)
        procs.append((folder, port, p))
        print(f"  -> Launched {folder} on http://127.0.0.1:{port} (PID {p.pid})")
    return procs


if __name__ == "__main__":
    print("🧦⚙️🧦 Booting One Big Backend Walk-In Demo Switchboard...")
    children = start_all_subservices()
    time.sleep(1.0)
    print("\n✅ ALL SERVICES LIVE! Open http://127.0.0.1:5050 in your browser for tomorrow's walk-ins!\n")
    try:
        app.run(host="127.0.0.1", port=5050, use_reloader=False)
    finally:
        for _, _, p in children:
            p.terminate()
