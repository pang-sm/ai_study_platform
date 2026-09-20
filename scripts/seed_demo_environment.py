"""ACCEL_PRODUCT_S10 PART F — the reproducible DEMO / ACCEPTANCE environment.

WHAT THIS IS FOR
----------------
Showing the complete product — a learner with a history — without inventing a single fact in
the real dataset. The demo needs attempts, a wrong answer, a study plan, learning records and
StudentTwin-eligible events; every one of those is indistinguishable, row for row, from a real
learner's. So they are produced in a SEPARATE database by a SEPARATE server process that
declares its origin, and every fact it writes is stamped ``DEMO``.

    DATA_ORIGIN=DEMO  DATABASE_URL=sqlite:///<demo.db>  uvicorn main:app --port 8021
    python scripts/seed_demo_environment.py --base http://127.0.0.1:8021 --db <demo.db>

DEMO_DATA_USED_FOR_MODEL_TRAINING = NO IS ENFORCED, NOT ASSUMED
---------------------------------------------------------------
This script does not trust the environment variable. It drives the real product over HTTP,
then reads the database back and FAILS if any row the demo account produced is not stamped
``DEMO``. Finally it runs the product's own KT export against that database and asserts the
demo learner contributes ZERO interactions to it — which is the gate itself, measured on the
artefacts rather than argued from the configuration.

The reverse failure is refused too: ``data_plane.origin`` refuses a non-LEARNER origin in
production, so a demo server misconfigured against the production database stamps
``UNCLASSIFIED`` and the export check below still excludes it. Running this against
production is refused outright before anything is written.

WHAT IS SET UP DIRECTLY, AND WHY
--------------------------------
One fixture row: the demo learner account. It exists in production only through a flow that
needs a real mailbox, so it is inserted with the application's own ``auth.hash_password`` and
then logged in through ``POST /login``. Every PRODUCT fact below is produced over HTTP, by
the real routes.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx  # noqa: E402

MODULE = "computer_network"
LEAF = "3.6"                      # the canonical leaf S8 made reachable
PASSWORD = "secret123"
DEMO_USERNAME = "demo_cs408"          # the account a demo/video uses. Left on FREE.
ACCEPTANCE_USERNAME = "demo_acceptance"  # the account the redeem→unlock proof runs on.
DEMO_CODE = "DEMO-CS408-STANDARD"

# A production database path is refused before anything is written. The demo environment is a
# different deployment with a different database; pointing this at the real one is the single
# mistake that would put demonstration facts in front of real analytics.
PRODUCTION_DB_MARKERS = ("/var/lib/ai_study_platform", "app.db")

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    line = f"{name}{(' — ' + detail) if detail else ''}"
    (PASS if condition else FAIL).append(line)
    print(f"  {'PASS' if condition else 'FAIL'}  {line}")
    return bool(condition)


def refuse_production(db_path: Path, base: str) -> None:
    resolved = str(db_path.resolve()).replace("\\", "/")
    for marker in PRODUCTION_DB_MARKERS:
        if marker in resolved:
            raise SystemExit(
                f"REFUSED: {resolved} looks like a production database ({marker!r}).\n"
                "The demo environment must use its own database — see this script's "
                "docstring.")
    if "localhost" not in base and "127.0.0.1" not in base:
        raise SystemExit(
            f"REFUSED: {base} is not a local address. The demo seed path only ever talks to "
            "a demo server on this machine.")


def seed_demo_account(db_path: Path, username: str) -> None:
    """Fixture row 1 of 2. Idempotent: an existing account is reused, not duplicated."""
    import auth

    con = sqlite3.connect(db_path)
    try:
        row = con.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            print(f"  account {username!r} already exists (id={row[0]}); reusing it")
            return
        con.execute(
            "INSERT INTO users (username, hashed_password, grade, major, is_admin) "
            "VALUES (?, ?, 'senior', '软件工程', 0)",
            (username, auth.hash_password(PASSWORD)))
        con.commit()
        print(f"  created account {username!r}")
    finally:
        con.close()


def seed_demo_code(db_path: Path, code: str) -> None:
    """Fixture row 2 of 2: one redemption code.

    A redemption code exists in production only because an operator minted one, so a
    rehearsal cannot obtain it over HTTP. It grants the rank-1 per-direction plan, which maps
    to the `standard` tier — the exact code a demo types on camera.
    """
    import membership

    con = sqlite3.connect(db_path)
    try:
        digest = membership.hash_code(code)
        row = con.execute("SELECT id FROM redemption_codes WHERE code_hash = ?",
                          (digest,)).fetchone()
        if row:
            print(f"  redemption code {code!r} already exists; reusing it")
            return
        con.execute(
            "INSERT INTO redemption_codes (code_hash, service_key, target_plan, "
            "membership_duration_days, plan_code, max_uses, used_count, status, created_by) "
            "VALUES (?, 'exam_11408', 'monthly_sprint', 30, 'monthly_sprint', 50, 0, "
            "'active', 's10_demo_seed')",
            (digest,))
        con.commit()
        print(f"  created redemption code {code!r} (grants Standard, 30 days)")
    finally:
        con.close()


class Learner:
    def __init__(self, base: str, username: str):
        self.http = httpx.Client(base_url=base.rstrip("/"), timeout=30.0,
                                 follow_redirects=True)
        self.username = username

    def login(self) -> bool:
        return self.http.post("/login", json={"username": self.username,
                                              "password": PASSWORD}).status_code == 200


def build_demo_history(learner: Learner) -> dict:
    """Produce the demo history over the REAL product routes. Returns a fact summary."""
    facts: dict = {}

    plan = learner.http.get(f"/exam/11408/subjects/{MODULE}/study-plan")
    facts["study_plan_status"] = plan.status_code

    listing = learner.http.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                              params={"knowledge_point_id": LEAF})
    items = listing.json().get("items") or []
    facts["questions_available"] = len(items)
    if not items:
        return facts

    question = items[0]
    created = learner.http.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                               json={"question_ids": [question["id"]],
                                     "knowledge_point_id": LEAF})
    if created.status_code != 200:
        facts["attempt_status"] = created.status_code
        return facts
    attempt_id = created.json()["attempt_id"]
    facts["attempt_id"] = attempt_id

    # ONE WRONG ANSWER, deliberately: a wrong answer is what produces the wrong-answer record
    # and a NEGATIVE label. All-correct demo data would leave the wrong-answer surface empty
    # and every label on one side.
    correct = question.get("standard_answer") or "A"
    wrong = next((o for o in ("A", "B", "C", "D") if o != correct), "B")
    learner.http.post(
        f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/answers",
        json={"answers": {str(question["id"]): wrong}})
    submitted = learner.http.post(
        f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/submit",
        json={"answers": {str(question["id"]): wrong}})
    facts["submit_status"] = submitted.status_code

    wrong_answers = learner.http.get("/wrong-answers",
                                     params={"service_namespace": "exam_prep",
                                             "module": MODULE})
    facts["wrong_answers"] = len((wrong_answers.json().get("items") or []))

    records = learner.http.get("/learning-records", params={"service_namespace": "exam_prep"})
    facts["learning_records"] = records.status_code

    twin = learner.http.get("/exam/prep/scientific/student-twin",
                            params={"exam_module_id": MODULE})
    facts["student_twin_status"] = twin.status_code

    return facts


def entitlement(learner: Learner, service_key: str = "exam_11408") -> dict:
    response = learner.http.get("/membership/entitlements",
                               params={"service_key": service_key})
    return response.json() if response.status_code == 200 else {"error": response.status_code}


def rehearse_plan_unlock(learner: Learner, code: str) -> dict:
    """ACCEL_PRODUCT_S10 PART D/M — the real end-to-end proof, on a demo environment.

        Free → entitlements say locked → redeem → entitlements say allowed → the Plan loads

    Every step is a real request against the real server. Nothing is simulated and no state is
    forced: the ONLY thing that changes between the two reads is the redeem.
    """
    before_ent = entitlement(learner)
    before_plan = learner.http.get(f"/exam/11408/subjects/{MODULE}/study-plan")
    before = {
        "tier": before_ent.get("current_tier"),
        "plan_allowed": (before_ent.get("features") or {}).get("learning_plan", {}).get("allowed"),
        "study_plan_http": before_plan.status_code,
    }

    redeemed = learner.http.post("/subscription/redeem", json={"code": code})

    after_ent = entitlement(learner)
    after_plan = learner.http.get(f"/exam/11408/subjects/{MODULE}/study-plan")
    after = {
        "redeem_http": redeemed.status_code,
        "redeem_body": redeemed.json() if redeemed.status_code == 200 else None,
        "tier": after_ent.get("current_tier"),
        "plan_allowed": (after_ent.get("features") or {}).get("learning_plan", {}).get("allowed"),
        "study_plan_http": after_plan.status_code,
    }
    return {"before": before, "after": after}


def verify_origin(db_path: Path, username: str) -> dict:
    """Read the demo facts BACK and report what origin they actually carry. No assumptions."""
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        user = con.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            return {"error": "demo account missing"}
        user_id = user[0]
        result = {"user_id": user_id}
        for table in ("learning_events", "practice_attempts"):
            rows = con.execute(
                f"SELECT data_origin, COUNT(*) FROM {table} WHERE user_id = ? "
                f"GROUP BY data_origin", (user_id,)).fetchall()
            result[table] = {str(origin): count for origin, count in rows}
        result["learner_origin_rows"] = con.execute(
            "SELECT (SELECT COUNT(*) FROM learning_events WHERE user_id = ? AND "
            "data_origin = 'LEARNER') + (SELECT COUNT(*) FROM practice_attempts WHERE "
            "user_id = ? AND data_origin = 'LEARNER')", (user_id, user_id)).fetchone()[0]
        return result
    finally:
        con.close()


def verify_excluded_from_training(db_path: Path, user_ids: list[int]) -> dict:
    """Run the PRODUCT'S OWN export against the demo database.

    This is the hard gate: DEMO_DATA_USED_FOR_MODEL_TRAINING = NO, measured on the dataset
    the exporter would actually produce rather than on the configuration that produced it.
    """
    from science import kt_dataset  # lazy: main() already bound DATABASE_URL to the demo DB
    import database
    session = database.SessionLocal()
    try:
        coverage = kt_dataset.interaction_coverage(session, service_namespace="exam_prep")
        demo_refs = {str(kt_dataset.learner_ref(uid)) for uid in user_ids}
        body = kt_dataset.build(session, service_namespace="exam_prep")
        exported_learners = {s["learner_ref"] for s in body.get("sequences") or []}
        return {
            "excluded": coverage["excluded"],
            "demo_interactions": coverage["demo_interactions"],
            "real_eligible_interactions": coverage["real_eligible_interactions"],
            "demo_learner_ref_exported": bool(demo_refs & exported_learners),
            "sequences": len(body.get("sequences") or []),
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8021",
                        help="base URL of the running DEMO server")
    parser.add_argument("--db", required=True,
                        help="path to the database the demo server is using")
    parser.add_argument("--username", default=DEMO_USERNAME)
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    refuse_production(db_path, args.base)

    # Bound BEFORE any application import: `database.py` reads DATABASE_URL once, at import
    # time, so a later assignment would leave the export check reading a different database
    # than the one that was just seeded — and it would pass for the wrong reason.
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

    print(f"=== demo seed against {args.base} (db={db_path}) ===\n")
    seed_demo_account(db_path, args.username)
    seed_demo_account(db_path, ACCEPTANCE_USERNAME)
    seed_demo_code(db_path, DEMO_CODE)

    learner = Learner(args.base, args.username)
    if not learner.login():
        print("FAIL  could not log in as the demo account", file=sys.stderr)
        return 1

    print("\n-- product history, produced over HTTP --")
    facts = build_demo_history(learner)
    for key, value in facts.items():
        print(f"  {key} = {value}")

    # The demo account stays on FREE, so the recorded demo has a lock to open on camera.
    demo_ent = entitlement(learner)
    check("the demo account starts LOCKED, so the demo has a real lock to open",
          (demo_ent.get("features") or {}).get("learning_plan", {}).get("allowed") is False,
          f"tier={demo_ent.get('current_tier')}")
    print(f"  redemption code for the demo: {DEMO_CODE}")

    print("\n-- PART M rehearsal: the full journey, on the acceptance account --")
    acceptance = Learner(args.base, ACCEPTANCE_USERNAME)
    if not acceptance.login():
        print("FAIL  could not log in as the acceptance account", file=sys.stderr)
        return 1
    journey = build_demo_history(acceptance)
    for key in ("study_plan_status", "questions_available", "submit_status",
                "wrong_answers", "learning_records", "student_twin_status"):
        check(f"acceptance: {key}", journey.get(key) is not None, str(journey.get(key)))
    unlock = rehearse_plan_unlock(acceptance, DEMO_CODE)
    print(f"  before = {unlock['before']}")
    print(f"  after  = {unlock['after']}")
    check("the Plan is LOCKED before the redeem",
          unlock["before"]["plan_allowed"] is False
          and unlock["before"]["study_plan_http"] == 403,
          str(unlock["before"]))
    check("the redeem succeeds", unlock["after"]["redeem_http"] == 200,
          str(unlock["after"]["redeem_body"]))
    check("the entitlement reflects the new tier IMMEDIATELY",
          unlock["after"]["plan_allowed"] is True
          and unlock["after"]["tier"] == "standard",
          str(unlock["after"]))
    check("the Plan OPENS — no success reported while the lock stays closed",
          unlock["after"]["study_plan_http"] == 200,
          f"http={unlock['after']['study_plan_http']}")
    check("REDEEM_SUCCESS_WITH_LOCK_STILL_CLOSED = 0",
          not (unlock["after"]["redeem_http"] == 200
               and unlock["after"]["plan_allowed"] is not True))

    print("\n-- provenance, read back from the database --")
    user_ids = []
    for username in (args.username, ACCEPTANCE_USERNAME):
        record = verify_origin(db_path, username)
        user_ids.append(record.get("user_id"))
        print(f"  {username}: learning_events={record.get('learning_events')} "
              f"practice_attempts={record.get('practice_attempts')}")

        check(f"{username}: produced facts at all",
              sum(sum(v.values()) for k, v in record.items() if isinstance(v, dict)) > 0,
              str(record))
        check(f"{username}: no fact leaked in as LEARNER",
              record.get("learner_origin_rows") == 0,
              f"LEARNER rows = {record.get('learner_origin_rows')}")
        seen = {value for table in ("learning_events", "practice_attempts")
                for value in (record.get(table) or {})}
        check(f"{username}: the origin stamped is DEMO and nothing else",
              seen == {"DEMO"}, f"origins seen: {sorted(seen)}")

    print("\n-- the training gate, measured on the product's own export --")
    if any(uid is None for uid in user_ids):
        print("FAIL  a demo user id is missing; cannot run the export check")
        return 1
    export = verify_excluded_from_training(db_path, user_ids)
    print(f"  excluded = {export['excluded']}")
    print(f"  demo_interactions = {export['demo_interactions']}")
    print(f"  real_eligible_interactions = {export['real_eligible_interactions']}")

    check("DEMO_DATA_USED_FOR_MODEL_TRAINING = NO",
          export["demo_learner_ref_exported"] is False,
          "a demo learner appears in the export" if export["demo_learner_ref_exported"]
          else "no demo learner appears in the export")
    check("the demo facts were excluded by ORIGIN, not merely unused",
          any(str(k).startswith("DATASET_ORIGIN_") for k in (export["excluded"] or {})),
          str(export["excluded"]))

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    for line in FAIL:
        print(f"  FAILED: {line}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
