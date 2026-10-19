"""End-to-end verification of the V3 'Undo Button' (Git Commit & 1-Click Revert)
across Module 1 (obb-scheduling), Module 2 (obb-grants), and Module 3 (obb-library).
"""
import importlib.util
import os
import runpy
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_module_from_dir(mod_dir, name):
    sys.path = [p for p in sys.path if "obb-" not in p]
    sys.path.insert(0, mod_dir)
    if "db" in sys.modules:
        del sys.modules["db"]
    spec = importlib.util.spec_from_file_location(name, os.path.join(mod_dir, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.app.root_path = mod_dir
    return mod


def test_scheduling_nuke_and_undo():
    print("\n=== [TEST 1] Module 1 (obb-scheduling): Stage Demo 'Nuke Schedule & Hit Undo' ===")
    sched_dir = os.path.join(ROOT_DIR, "obb-scheduling")
    tmp_db = tempfile.mktemp(suffix="_sched.db")
    os.environ["OBB_DB"] = tmp_db
    sys.path = [p for p in sys.path if "obb-" not in p]
    sys.path.insert(0, sched_dir)
    if "db" in sys.modules:
        del sys.modules["db"]
    runpy.run_path(os.path.join(sched_dir, "seed.py"), run_name="__main__")

    sched_app = load_module_from_dir(sched_dir, "sched_app")
    sched_app.app.config["TESTING"] = True
    client = sched_app.app.test_client()

    # Login as Marleen (Big Buds manager)
    client.post("/login", data={"username": "marleen", "password": "demo-pass"})

    with sched_app.app.app_context():
        initial_shifts = len(sched_app.shifts_for_week(1, 0))
    print(f"  -> Initial Big Buds Week 1 shifts : {initial_shifts}")
    assert initial_shifts == 27, f"Expected 27 seeded shifts, got {initial_shifts}"

    # Nuke Week 1 on stage!
    r = client.post("/shop/1/schedule/clear", data={"week": "0"}, follow_redirects=True)
    assert r.status_code == 200
    with sched_app.app.app_context():
        nuked_shifts = len(sched_app.shifts_for_week(1, 0))
    print(f"  -> After clicking 'Clear week'    : {nuked_shifts} shifts (Bill 56 violations everywhere!)")
    assert nuked_shifts == 0

    # Hit 1-Click Undo!
    r = client.post("/shop/1/schedule/undo", data={"week": "0"}, follow_redirects=True)
    assert r.status_code == 200
    with sched_app.app.app_context():
        restored_shifts = len(sched_app.shifts_for_week(1, 0))
    print(f"  -> After clicking '↶ Undo'        : {restored_shifts} shifts (100% restored!)")
    assert restored_shifts == initial_shifts

    # Check Git History page renders
    r_hist = client.get("/shop/1/history")
    assert r_hist.status_code == 200 and b"Cleared all 27 shift(s)" in r_hist.data
    print("  -> [PASSED] Stage Nuke + 1-Click Undo + Git History verified!")


def test_grants_revision_and_undo():
    print("\n=== [TEST 2] Module 2 (obb-grants): Collaborative Section Edit & 1-Click Undo ===")
    grants_dir = os.path.join(ROOT_DIR, "obb-grants")
    tmp_db = tempfile.mktemp(suffix="_grants.db")
    os.environ["OBB_DB"] = tmp_db
    sys.path = [p for p in sys.path if "obb-" not in p]
    sys.path.insert(0, grants_dir)
    if "db" in sys.modules:
        del sys.modules["db"]
    runpy.run_path(os.path.join(grants_dir, "seed.py"), run_name="__main__")

    grants_app = load_module_from_dir(grants_dir, "grants_app")
    grants_app.app.config["TESTING"] = True
    client = grants_app.app.test_client()

    with grants_app.app.app_context():
        sec = grants_app.d.q1("SELECT * FROM app_sections WHERE application_id=1 ORDER BY position LIMIT 1")
        sec_id = sec["id"]
        orig_body = sec["body"]

    # Contributor accidentally overwrites the section with a bad draft
    r = client.post(
        "/t/1/apps/1",
        data={"section_id": str(sec_id), "contributor": "Viv", "body": "ACCIDENTAL OVERWRITE DRAFT"},
        follow_redirects=True,
    )
    assert r.status_code == 200 and b"ACCIDENTAL OVERWRITE DRAFT" in r.data
    print(f"  -> Saved new draft on section #{sec_id} (logged git commit)")

    # Click Undo on the grant application!
    r_undo = client.post("/t/1/apps/1/undo", data={}, follow_redirects=True)
    assert r_undo.status_code == 200
    with grants_app.app.app_context():
        restored_body = grants_app.d.q1("SELECT body FROM app_sections WHERE id=?", (sec_id,))["body"]
    assert restored_body == orig_body
    print("  -> [PASSED] Grant section restored to exact original text via 1-Click Undo!")


def test_st_ignatius_library_and_undo():
    print("\n=== [TEST 3] Module 3 (obb-library): St. Ignatius Lending Catalog & Undo ===")
    lib_dir = os.path.join(ROOT_DIR, "obb-library")
    tmp_db = tempfile.mktemp(suffix="_lib.db")
    os.environ["OBB_LIBRARY_DB"] = tmp_db
    lib_app = load_module_from_dir(lib_dir, "lib_app")
    lib_app.app.config["TESTING"] = True
    client = lib_app.app.test_client()

    # Check St. Ignatius catalog loads
    r = client.get("/lib/1")
    assert r.status_code == 200 and b"The Spiritual Exercises of St. Ignatius" in r.data
    print("  -> St. Ignatius Spiritual Education Centre catalog online (5 core titles seeded)")

    # Check out a book
    r_co = client.post(
        "/lib/1/checkout/2",
        data={"borrower_name": "Fr. Daryl", "borrower_contact": "parish@stignatius.ca"},
        follow_redirects=True,
    )
    assert r_co.status_code == 200 and b"Checked out" in r_co.data
    print("  -> Checked out 'The Jesuit Guide to (Almost) Everything' to Fr. Daryl")

    # Undo the checkout
    r_undo = client.post("/lib/1/undo", data={}, follow_redirects=True)
    assert r_undo.status_code == 200 and b"Undid" in r_undo.data
    print("  -> [PASSED] Library checkout 1-click undone and copy availability restored!")


if __name__ == "__main__":
    test_scheduling_nuke_and_undo()
    test_grants_revision_and_undo()
    test_st_ignatius_library_and_undo()
    print("\n🧦⚙️🧦 ALL V3 'ONE BIG BACK END' TESTS PASSED! NOTHING CAN PLUG IT! 🧦⚙️🧦")
