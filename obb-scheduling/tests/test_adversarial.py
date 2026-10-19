"""OBB Scheduling Module 1 — adversarial tenancy/security tests.

These tests ATTACK the app. Each check names the attack, the expected
defense, and PASS/FAIL. Runs against a throwaway temp DB.
"""
import os
import sys
import tempfile

TMPDB = tempfile.mktemp(suffix=".db")
os.environ["OBB_DB"] = TMPDB
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import runpy
runpy.run_path(os.path.join(os.path.dirname(__file__), "..", "seed.py"),
               run_name="__main__")

import app as A
import db as d

A.app.config["TESTING"] = True
client = A.app.test_client()

results = []


def attack(name, cond, note=""):
    results.append((name, bool(cond), note))
    assert cond, "ATTACK SUCCEEDED (defense failed): %s %s" % (name, note)


def login(username, password="demo-pass"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


def logout():
    client.get("/logout")


def ctx():
    return A.app.app_context()


# ---------- A1: cross-tenant read — staff of shop 1 GETs shop 2 ----------
login("josh")  # Big Buds staff
r = client.get("/shop/2", follow_redirects=False)
attack("A1 cross-tenant GET -> 403", r.status_code == 403,
       "got %s" % r.status_code)
r = client.get("/shop/2/schedule", follow_redirects=False)
attack("A1b cross-tenant schedule GET -> 403", r.status_code == 403,
       "got %s" % r.status_code)

# ---------- A2: cross-tenant write — staff of shop 1 POSTs into shop 2 ----------
r = client.post("/shop/2/shifts/add",
                data={"employee_id": "1", "day": "0", "start": "09:00", "end": "17:00"},
                follow_redirects=False)
attack("A2 cross-tenant POST -> 403", r.status_code == 403,
       "got %s" % r.status_code)

# ---------- A3: privilege escalation — staff hits manager-only route ----------
r = client.post("/shop/1/shifts/add",
                data={"employee_id": "1", "day": "0", "start": "09:00", "end": "17:00"},
                follow_redirects=False)
attack("A3 staff POST manager route -> 403", r.status_code == 403,
       "got %s" % r.status_code)
r = client.get("/shop/1/settings", follow_redirects=False)
attack("A3b staff GET manager page -> 403", r.status_code == 403,
       "got %s" % r.status_code)
r = client.post("/shop/1/timeoff/1/approve", follow_redirects=False)
attack("A3c staff POST approval route -> 403", r.status_code == 403,
       "got %s" % r.status_code)
logout()

# ---------- A4: tampered session cookie ----------
login("josh")
sess = client.get_cookie("session").value
# flip characters in the middle of the signed payload
mid = len(sess) // 2
tampered = sess[:mid] + ("A" if sess[mid] != "A" else "B") + sess[mid + 1:]
logout()
client.set_cookie("session", tampered)
r = client.get("/shop/1", follow_redirects=False)
attack("A4 tampered session cookie rejected (not 200)",
       r.status_code != 200, "got %s" % r.status_code)
attack("A4b tampered cookie -> login redirect",
       r.status_code == 302 and "/login" in r.headers.get("Location", ""),
       "got %s -> %s" % (r.status_code, r.headers.get("Location", "")))
client.delete_cookie("session")

# ---------- A5: SQL injection at login ----------
r = client.post("/login",
                data={"username": "' OR '1'='1", "password": "anything"},
                follow_redirects=False)
attack("A5 SQLi login rejected", r.status_code == 200,
       "got %s" % r.status_code)  # 200 = login page re-rendered (failed)
r = client.get("/", follow_redirects=False)
attack("A5b SQLi login set no session (still on login)",
       r.status_code == 200, "got %s" % r.status_code)
r = client.post("/login",
                data={"username": "marleen'; DROP TABLE users;--", "password": "x"},
                follow_redirects=False)
with ctx():
    n = d.q1("SELECT COUNT(*) c FROM users")["c"]
attack("A5c users table intact after injection", n == 6, "count=%s" % n)

# ---------- A6: SQL injection in stored fields ----------
login("marleen")  # Big Buds manager
evil = "Big Buds'); DROP TABLE shops;--"
r = client.post("/shop/1/settings",
                data={"name": evil, "open": "09:00", "close": "23:00", "budget": "5000"},
                follow_redirects=False)
with ctx():
    shops = d.q("SELECT * FROM shops")
    names = [s["name"] for s in shops]
attack("A6 shops table intact after stored injection",
       len(shops) == 2 and evil in names,
       "shops=%s" % names)
# restore the demo name
client.post("/shop/1/settings",
            data={"name": "Big Buds", "open": "09:00", "close": "23:00", "budget": "5000"})
logout()

# ---------- A7: unauthenticated direct access ----------
r = client.get("/shop/1", follow_redirects=False)
attack("A7 unauthenticated /shop/1 -> login redirect (not 200)",
       r.status_code == 302 and "/login" in r.headers.get("Location", ""),
       "got %s" % r.status_code)

# ---------- A8: open redirect after login ----------
r = client.post("/login", data={"username": "josh", "password": "demo-pass",
                                "next": "https://evil.example/phish"},
                follow_redirects=False)
loc = r.headers.get("Location", "")
attack("A8 evil 'next' not honored",
       r.status_code == 302 and loc.startswith("/shop/"),
       "Location: %s" % loc)
r = client.post("/login", data={"username": "josh", "password": "demo-pass",
                                "next": "//evil.example/phish"},
                follow_redirects=False)
loc = r.headers.get("Location", "")
attack("A8b protocol-relative 'next' not honored",
       r.status_code == 302 and loc.startswith("/shop/") and "evil" not in loc,
       "Location: %s" % loc)
logout()

# ---------- A9: cookie flags ----------
r = client.post("/login", data={"username": "josh", "password": "demo-pass"},
                follow_redirects=False)
set_cookie = r.headers.get("Set-Cookie", "")
attack("A9 session cookie HttpOnly", "HttpOnly" in set_cookie, set_cookie)
attack("A9b session cookie SameSite", "SameSite" in set_cookie, set_cookie)
logout()

print("ADVERSARIAL (scheduling): %d attacks, all defended." % len(results))
for name, ok, note in results:
    print("  PASS  %s" % name)
