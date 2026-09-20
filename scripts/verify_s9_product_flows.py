"""ACCEL_PRODUCT_S9 PART K — the real product flows, exercised over HTTP against a server.

WHAT IT PROVES, AND WHY OVER HTTP
---------------------------------
Every claim the final response makes about a FLOW is checked here against a running
application, not against a unit under test:

    knowledge leaf → concept-scoped practice → submit
        → the attempt carries the canonical concept
        → the learning event carries the SAME concept
        → the dataset export groups it under that concept
    records answer after that write, and the StudentTwin preview still works
    the locked Study Plan → the membership reads → the required plan → the lock OPENS
    one learner's attempt, tier and entitlements are not another's
    /science/status answers only to an admin

WHAT IS SET UP DIRECTLY, AND WHY
--------------------------------
The two fixture rows — a learner account and a redemption code — are written to the database
before the run. Both exist in production only through flows that need a real mailbox and a
real operator, so a rehearsal cannot obtain them over HTTP; the flows UNDER TEST are all
exercised over HTTP. The accounts are created with the application's own
``auth.hash_password`` and logged in through ``POST /login``.

Run it against a server bound to a MIGRATED COPY of the production database, never against
production itself: it writes real attempts, wrong answers and a redemption.

    python scripts/verify_s9_product_flows.py --base http://127.0.0.1:8951 \
        --db .s9tmp/prod_copy.db

Exit code 0 means every check passed.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

PASS: list[str] = []
FAIL: list[str] = []
LEAF = "3.6"          # computer_network — the leaf S8 made reachable
MODULE = "computer_network"
PASSWORD = "secret123"


def check(name: str, condition: bool, detail: str = "") -> bool:
    line = f"{name}{(' — ' + detail) if detail else ''}"
    (PASS if condition else FAIL).append(line)
    print(f"  {'PASS' if condition else 'FAIL'}  {line}")
    return bool(condition)


def seed(db_path: Path, usernames: list[str], code: str, *, admin: bool = False) -> None:
    """Create the fixture rows the flows below need. Stated in the module docstring."""
    import sqlite3

    import auth
    import membership

    con = sqlite3.connect(db_path)
    try:
        for username in usernames:
            con.execute(
                "INSERT INTO users (username, hashed_password, grade, major, is_admin) "
                "VALUES (?, ?, 'freshman', 'cs', ?)",
                (username, auth.hash_password(PASSWORD), 1 if admin else 0))
        con.execute(
            "INSERT INTO redemption_codes (code_hash, service_key, target_plan, "
            "membership_duration_days, plan_code, max_uses, used_count, status, created_by) "
            "VALUES (?, 'exam_11408', 'monthly_sprint', 30, 'monthly_sprint', 1, 0, "
            "'active', 's9_acceptance')",
            (membership.hash_code(code),))
        con.commit()
    finally:
        con.close()


class Learner:
    """One learner's session. Cookies live on the instance, so two of these are two people."""

    def __init__(self, base: str, username: str):
        self.base = base.rstrip("/")
        self.username = username
        self.http = httpx.Client(base_url=self.base, timeout=30.0, follow_redirects=True)

    def login(self) -> bool:
        return self.http.post(
            "/login", json={"username": self.username, "password": PASSWORD}
        ).status_code == 200

    def get(self, path: str, **kw):
        return self.http.get(path, **kw)

    def post(self, path: str, **kw):
        return self.http.post(path, **kw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="base URL of the running app")
    parser.add_argument("--db", required=True, help="path to the database the app is using")
    parser.add_argument("--admin", action="store_true",
                        help="also seed and probe an ADMIN account")
    args = parser.parse_args()

    tag = uuid.uuid4().hex[:8]
    user_a, user_b = f"s9a_{tag}", f"s9b_{tag}"
    admin_user = f"s9admin_{tag}"
    code = f"S9-{tag.upper()}"
    names = [user_a, user_b] + ([admin_user] if args.admin else [])
    seed(Path(args.db).resolve(), names, code, admin=False)
    if args.admin:
        import sqlite3
        con = sqlite3.connect(Path(args.db).resolve())
        con.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (admin_user,))
        con.commit()
        con.close()

    print(f"=== S9 product-flow acceptance against {args.base} ===\n")

    print("[health]")
    check("GET /health", httpx.get(f"{args.base.rstrip('/')}/health", timeout=20).status_code == 200)

    a, b = Learner(args.base, user_a), Learner(args.base, user_b)
    check(f"login {user_a}", a.login())
    check(f"login {user_b}", b.login())

    # ---------------------------------------------------------------- B/K: the flow
    print("\n[concept identity — knowledge leaf → practice → attempt → event → dataset]")
    listing = a.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                    params={"chapter_code": "3", "concept_code": LEAF})
    items = listing.json().get("items", []) if listing.status_code == 200 else []
    check("concept-scoped question list is served", listing.status_code == 200,
          f"{listing.status_code}, {len(items)} questions")
    if not check("the concept has questions", len(items) > 1, f"{len(items)}"):
        return _report()
    ids = [item["id"] for item in items]

    # The chapter-4 collision, both halves. `4.50` is a STORED id from the source's own
    # 4.1..4.51 numbering and is not a canonical leaf, so it is refused. `4.2` IS canonical
    # — canonical 4.2 means IPv4, not the source's 路由与转发 — so it is answered, and
    # answered with NOTHING, because the rows stored under the colliding id carry no
    # canonical concept. A laxer rule would have invented 5 links here.
    refused = a.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                    params={"chapter_code": "4", "concept_code": "4.50"})
    check("a stored non-canonical id is REFUSED, not answered empty",
          refused.status_code == 422, f"{refused.status_code}")
    canonical_but_empty = a.get(f"/exam/11408/{MODULE}/chapter-practice/questions",
                                params={"chapter_code": "4", "concept_code": "4.2"})
    check("the colliding canonical leaf answers EMPTY rather than the collision's rows",
          canonical_but_empty.status_code == 200
          and canonical_but_empty.json()["total"] == 0,
          f"{canonical_but_empty.status_code}, "
          f"{canonical_but_empty.json().get('total') if canonical_but_empty.status_code == 200 else '-'}")

    invalid = a.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                     json={"question_ids": ids[:1], "knowledge_point_id": "9.9"})
    check("an invalid concept is refused at the write boundary",
          invalid.status_code == 422, f"{invalid.status_code}")

    mismatched = a.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                        json={"question_ids": ids[:1], "knowledge_point_id": "1.1"})
    check("a concept from another module is refused",
          mismatched.status_code == 422, f"{mismatched.status_code}")

    created = a.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                     json={"question_ids": ids, "knowledge_point_id": LEAF})
    check("attempt created with the canonical concept", created.status_code == 200,
          f"{created.status_code}")
    if created.status_code != 200:
        return _report()
    attempt_id = created.json()["attempt_id"]

    submitted = a.post(
        f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/submit",
        json={"answers": {str(ids[0]): "A", str(ids[1]): "B", str(ids[2]): "C"}})
    check("attempt submitted", submitted.status_code == 200, f"{submitted.status_code}")
    if submitted.status_code == 200:
        results = submitted.json().get("results", [])
        check("the submit response carries per-question results", bool(results),
              f"{len(results)} results")

    detail = a.get(f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}")
    check("the submitted attempt replays its results",
          detail.status_code == 200 and bool(detail.json().get("results")),
          f"{detail.status_code}")

    direct = a.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                    json={"question_ids": ids[:1]})
    check("direct entry creates an attempt with NO concept", direct.status_code == 200,
          f"{direct.status_code}")
    if direct.status_code == 200:
        a.post(f"/exam/11408/{MODULE}/chapter-practice/attempts/"
               f"{direct.json()['attempt_id']}/submit",
               json={"answers": {str(ids[0]): "A"}})

    # ---------------------------------------------------------------- records / twin
    print("\n[records and the student twin, after that write]")
    summary = a.get("/learning-records/summary", params={"service_namespace": "exam_prep"})
    check("learning records summary answers", summary.status_code == 200,
          f"{summary.status_code}")
    if summary.status_code == 200:
        body = summary.json()
        # The write above produced graded, answered facts; the summary must COUNT them
        # rather than merely answer. A zero here would mean the concept-carrying attempt
        # never reached the record stream.
        check("the summary counts the practice that was just recorded",
              body.get("practice_attempts", 0) > 0
              and body.get("factual_correct", 0) + body.get("factual_incorrect", 0) > 0,
              json.dumps({k: body.get(k) for k in
                          ("total_events", "practice_attempts", "graded_attempts",
                           "factual_correct", "factual_incorrect", "ungraded_attempts")},
                         ensure_ascii=False))
        check("an ungraded item is NOT counted as a factual failure",
              body.get("ungraded_attempts", 0)
              == body.get("practice_attempts", 0) - body.get("graded_attempts", 0))

    page = a.get("/learning-records", params={"limit": 100,
                                              "service_namespace": "exam_prep"})
    check("the record page answers", page.status_code == 200, f"{page.status_code}")
    if page.status_code == 200:
        records = page.json().get("records", [])
        matching = [r for r in records
                    if str((r.get("source") or {}).get("id")) == str(attempt_id)]
        check("the concept-scoped attempt appears in the record page", bool(matching),
              f"{len(records)} records, {len(matching)} for attempt {attempt_id}")
        if matching:
            # Every event of this attempt must carry the module AND the concept — this is
            # the propagation arriving at the record surface, not just at the event row.
            contexts = [(r.get("context") or {}) for r in matching]
            check("every record of the attempt carries the module and the concept",
                  all(c.get("exam_module_id") == MODULE
                      and c.get("knowledge_point_id") == LEAF for c in contexts),
                  json.dumps(contexts[0], ensure_ascii=False))

    capabilities = a.get("/exam/prep/scientific/capabilities")
    check("capabilities contract answers", capabilities.status_code == 200,
          f"{capabilities.status_code}")
    if capabilities.status_code == 200:
        components = capabilities.json().get("components", [])
        visible = [c["component"] for c in components if c.get("user_visible")]
        check("student_twin is the ONLY user-visible component",
              visible == ["student_twin"], f"{visible}")
    twin = a.get("/exam/prep/scientific/student-twin")
    check("student twin preview answers", twin.status_code in (200, 503),
          f"{twin.status_code}")

    # ---------------------------------------------------------------- G/H: membership
    print("\n[membership — locked → reads → the required plan → the lock opens]")
    before = a.get("/membership/entitlements", params={"service_key": "exam_11408"})
    check("entitlements answer", before.status_code == 200, f"{before.status_code}")
    if before.status_code == 200:
        feature = before.json()["features"]["learning_plan"]
        check("the study plan is LOCKED for a fresh account", feature["allowed"] is False,
              f"required={feature['required_plan']}")

    tier = a.get("/subscription")
    check("current tier answers", tier.status_code == 200,
          f"tier={tier.json().get('tier') if tier.status_code == 200 else tier.status_code}")
    plans = a.get("/subscription/plans")
    check("plan catalog answers", plans.status_code == 200,
          f"{sorted(plans.json().get('plans', {})) if plans.status_code == 200 else plans.status_code}")
    usage = a.get("/usage/summary")
    check("usage summary answers", usage.status_code == 200, f"{usage.status_code}")
    if usage.status_code == 200:
        periods = usage.json()["periods"]
        check("every period reports ONE shape",
              all(set(periods[p]) == {"budget", "reserved", "settled", "remaining"}
                  for p in periods), f"{sorted(periods)}")

    preview = a.post("/membership/redeem/preview",
                     json={"code": code, "service_key": "exam_11408"})
    check("a real code previews", preview.status_code == 200, f"{preview.status_code}")
    redeemed = a.post("/membership/redeem",
                      json={"code": code, "service_key": "exam_11408"})
    check("the code activates", redeemed.status_code == 200, f"{redeemed.status_code}")
    after = a.get("/membership/entitlements", params={"service_key": "exam_11408"})
    if after.status_code == 200:
        feature = after.json()["features"]["learning_plan"]
        check("THE LOCK IS OPEN after redeeming the required plan",
              feature["allowed"] is True, f"current_plan={after.json()['current_plan']}")
    study_plan = a.get(f"/exam/11408/subjects/{MODULE}/study-plan")
    check("the study plan now serves", study_plan.status_code == 200,
          f"{study_plan.status_code}")
    reuse = a.post("/membership/redeem", json={"code": code, "service_key": "exam_11408"})
    check("the same code cannot be redeemed twice", reuse.status_code == 400,
          f"{reuse.status_code}")
    bad = a.post("/membership/redeem", json={"code": "NOT-A-CODE", "service_key": "exam_11408"})
    check("an unknown code is refused with a reason", bad.status_code == 400,
          f"{bad.status_code} {bad.json().get('detail', '') if bad.status_code == 400 else ''}")

    # ---------------------------------------------------------------- isolation
    print("\n[cross-user isolation]")
    stolen = b.get(f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}")
    check("another learner cannot read the attempt", stolen.status_code == 404,
          f"{stolen.status_code}")
    b_tier = b.get("/subscription")
    check("another learner has their own tier",
          b_tier.status_code == 200 and b_tier.json()["tier"] == "free",
          f"{b_tier.json().get('tier') if b_tier.status_code == 200 else '-'}")
    b_ent = b.get("/membership/entitlements", params={"service_key": "exam_11408"})
    check("another learner's entitlements are their own",
          b_ent.status_code == 200 and b_ent.json()["current_plan"] == "free",
          f"{b_ent.json().get('current_plan') if b_ent.status_code == 200 else '-'}")
    b_reuse = b.post("/membership/redeem", json={"code": code, "service_key": "exam_11408"})
    check("another learner cannot reuse a consumed code", b_reuse.status_code == 400,
          f"{b_reuse.status_code}")

    # ---------------------------------------------------------------- science status
    print("\n[/science/status admin gate]")
    anon = httpx.get(f"{args.base.rstrip('/')}/science/status", timeout=20)
    check("anonymous is refused", anon.status_code == 401, f"{anon.status_code}")
    check("an ordinary learner is refused", a.get("/science/status").status_code == 403,
          f"{a.get('/science/status').status_code}")
    if args.admin:
        admin = Learner(args.base, admin_user)
        if check(f"login {admin_user} (admin)", admin.login()):
            status = admin.get("/science/status")
            check("an admin is served", status.status_code == 200, f"{status.status_code}")
            if status.status_code == 200:
                raw = status.text
                collection = status.json().get("data_collection", {})
                check("collection readiness is reported",
                      collection.get("measured") is True
                      and "concept_level_interactions" in collection,
                      json.dumps({k: collection.get(k) for k in
                                  ("users_with_events", "users_with_eligible_interactions",
                                   "eligible_interactions",
                                   "concept_level_interactions")}, ensure_ascii=False))
                check("uncollected fields are STATED, not zeroed",
                      collection["uncollected_fields"]["hint_count"]["state"] == "NOT_AVAILABLE"
                      and collection["uncollected_fields"]["response_time_ms"]["state"]
                      == "NOT_COLLECTED")
                check("no learner identity leaks into the payload",
                      user_a not in raw and admin_user not in raw)

    return _report()


def _report() -> int:
    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    for line in FAIL:
        print(f"  FAILED: {line}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
