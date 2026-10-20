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


@app.route("/")
def index():
    from flask import request
    return render_template_string(HUB_HTML, modules=get_modules_for_host(request.host))


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
