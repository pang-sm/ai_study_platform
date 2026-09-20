"""FRONTEND_BLOCKER_BC8 — CS408 study-plan contract closure.

Gates this file exists to prove:

  * ONE truthful task status. Every reader of an `ExamStudyPlanTask` row computes the same
    `computed_status` for the same row at the same moment — the canonical plan list
    included, which used to short-circuit to `not_started`;
  * the plan task carries NO writable status, and a body that sends one is REFUSED loudly
    instead of silently accepted and ignored;
  * completing/mutating a plan task writes no mastery and resolves no wrong-answer state;
  * the settings object has ONE shape, shared by the read and the write;
  * the canonical plan surface stays behind its (frozen, deliberately unchanged)
    `exam_11408.learning_plan` entitlement, separately from the `planning.generate`
    capability — the two authorization layers are not conflated;
  * AI plan generation is a separate capability, never writes learner fact, and a failed
    generation cannot damage an existing plan.

Everything that touches a database builds a TEMP one. `backend/app.db` is opened read-only.
"""
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import grant_unified_tier, register_and_login
import database
import main
from models import (
    ExamStudyPlanChapterPractice,
    ExamStudyPlanSetting,
    ExamStudyPlanTask,
    User,
    UserKnowledgeProgress,
    UserServiceMembership,
)
from data_plane.models import LearningEvent
from learning.wrong_answers.models import WrongAnswerState
from usage import capabilities
from usage.models import AIRequest

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"
SEED_DIR = BACKEND_DIR / "seed_data" / "knowledge_maps"

MODULE = "operating_system"
PLAN = f"/exam/11408/subjects/{MODULE}/study-plan"
SUMMARY = "/exam/11408/study-plan/tasks/summary"
DASHBOARD = f"/exam/11408/subjects/{MODULE}/dashboard-summary"
KNOWLEDGE_ITEM = f"/exam/11408/subjects/{MODULE}/study-plan/knowledge-items"


# ---------------------------------------------------------------- helpers


def grant_exam_plan(username: str, plan: str = "monthly_sprint") -> None:
    """Grant the plan the way every real grant path does: by raising the UNIFIED tier.

    ACCEL_PRODUCT_S10: writing only the per-direction row records a plan and opens nothing,
    because the capability gate reads the tier. `plan` is kept as a parameter so callers read
    as "a plan was bought", and is translated through the same mapping the product uses.
    """
    from membership import tier_from_service_plan

    db = database.SessionLocal()
    try:
        grant_unified_tier(db, username, tier_from_service_plan("exam_11408", plan))
    finally:
        db.close()


def set_tier(username: str, tier: str) -> None:
    """Set the unified tier for a test account, opening its own session."""
    db = database.SessionLocal()
    try:
        grant_unified_tier(db, username, tier)
    finally:
        db.close()


def entitled(client, username: str) -> str:
    register_and_login(client, username)
    grant_exam_plan(username)
    assert client.post("/login", json={"username": username,
                                       "password": "secret123"}).status_code == 200
    return username


@pytest.fixture(autouse=True)
def no_direct_provider(monkeypatch):
    """No BC8 test may reach a provider outside the orchestrator's provider seam."""
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("BC8 reached a direct provider call")))


@pytest.fixture
def provider_double(monkeypatch):
    """Replace ONLY the outbound provider, below the orchestrator (§31).

    The real capability permission, router, qualified-model-pool selection, estimate,
    reserve, gateway and settlement all still run — `behavior` decides whether the
    provider succeeds or fails.
    """
    from ai.providers import FakeProvider

    def _install(behavior: str = "success") -> list:
        calls: list = []

        def _make(name: str):
            provider = FakeProvider(provider=name, behavior=behavior,
                                    input_tokens=50, output_tokens=50)
            inner = provider.complete

            def complete(spec):
                calls.append((provider.name, spec.capability))
                return inner(spec)

            provider.complete = complete
            return provider

        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _make)
        return calls

    return _install


@pytest.fixture(scope="module")
def seed_section() -> dict:
    """A real (section_title, section_code, leaf_code) triple from the module's seed map."""
    raw = json.loads((SEED_DIR / f"{MODULE}_11408.json").read_text(encoding="utf-8"))
    for chapter in raw.get("chapters") or []:
        for section in chapter.get("children") or []:
            leaves = section.get("children") or []
            if leaves and section.get("title") and leaves[0].get("code"):
                return {"title": section["title"], "code": section["code"],
                        "leaf": leaves[0]["code"]}
    raise AssertionError("the seed map must contain a section with a coded leaf")


def create_task(client, username: str, **kwargs) -> dict:
    """POST a legal task. A bound section implies `single`, a bare title implies `all`."""
    payload = {"username": username, "subject_key": MODULE, "title": "BC8 任务",
               "task_type": "knowledge", **kwargs}
    payload.setdefault("scope_type",
                       "single" if payload.get("knowledge_point_name") else "all")
    r = client.post(PLAN + "/tasks", json=payload)
    assert r.status_code == 200, r.text
    return r.json()["task"]


def task_in(items: list[dict], task_id: int) -> dict:
    return next(t for t in items if t["id"] == task_id)


def master_leaf(client, username: str, leaf_code: str) -> None:
    r = client.patch(f"{KNOWLEDGE_ITEM}/{leaf_code}",
                     json={"username": username, "subject_key": MODULE,
                           "course_id": f"{MODULE}_11408",
                           "knowledge_point_code": leaf_code, "status": "mastered"})
    assert r.status_code == 200, r.text


def plan_snapshot(db) -> tuple:
    """Everything about the plan that a mutation must not disturb."""
    return (
        db.query(ExamStudyPlanTask).count(),
        db.query(ExamStudyPlanChapterPractice).count(),
        db.query(UserKnowledgeProgress).count(),
        db.query(WrongAnswerState).count(),
        db.query(LearningEvent).count(),
        sorted((t.id, t.status, t.title, t.due_date) for t in db.query(ExamStudyPlanTask).all()),
    )


def learner_fact_snapshot(db) -> tuple:
    """Everything a plan write is forbidden to touch: tasks, progress, mastery, wrong state.

    AI-call AUDIT rows (`ai_requests`, the `ai_called` learning event) are deliberately NOT
    in here — recording that a capability ran is the AI boundary doing its job, not learner
    fact. They are asserted separately.
    """
    return (
        db.query(ExamStudyPlanTask).count(),
        db.query(ExamStudyPlanChapterPractice).count(),
        db.query(UserKnowledgeProgress).count(),
        db.query(WrongAnswerState).count(),
        sorted((t.id, t.status, t.title, t.due_date) for t in db.query(ExamStudyPlanTask).all()),
    )


# ================================================================ A. one status


def test_canonical_list_computes_the_same_status_as_every_other_reader(
        client, db_session, seed_section):
    """The list is the canonical surface; it must not be the one that lies.

    Before BC8 the list called `_serialize_task(t)` with no session, so every row came back
    `not_started` with an empty reason while `tasks/summary`, the dashboard projection and
    the create/update responses all computed `in_progress` for the very same row.
    """
    username = entitled(client, "bc8_status")
    task = create_task(client, username, title="学本节",
                       knowledge_point_name=seed_section["title"])
    master_leaf(client, username, seed_section["leaf"])

    listed = task_in(client.get(PLAN).json()["tasks"], task["id"])
    summary = task_in(client.get(SUMMARY).json()["tasks"], task["id"])
    dashboard = next(t for t in client.get(DASHBOARD).json()["today_plan"]
                     if t["id"] == task["id"])

    # a mastered leaf out of the section's total puts the task in progress, not not_started
    assert listed["computed_status"] == "in_progress", listed
    assert listed["completion_reason"], "the list must carry the real reason, not ''"

    assert listed["computed_status"] == summary["computed_status"]
    assert listed["completion_reason"] == summary["completion_reason"]
    assert listed["computed_status"] == dashboard["computed_status"]
    # SAME_TASK_SAME_MOMENT_STATUS_DIVERGENCE = 0
    assert {listed["computed_status"], summary["computed_status"],
            dashboard["computed_status"]} == {"in_progress"}


def test_mutation_responses_carry_the_same_computed_status(client, seed_section):
    """A write answer and a later read answer must agree about the same row."""
    username = entitled(client, "bc8_status_write")
    created = create_task(client, username, title="学本节",
                          knowledge_point_name=seed_section["title"])
    master_leaf(client, username, seed_section["leaf"])

    patched = client.patch(f"{PLAN}/tasks/{created['id']}",
                           json={"username": username, "subject_key": MODULE,
                                 "note": "备注"}).json()["task"]
    listed = task_in(client.get(PLAN).json()["tasks"], created["id"])

    assert patched["computed_status"] == listed["computed_status"] == "in_progress"
    assert patched["completion_reason"] == listed["completion_reason"]


def test_status_is_derived_not_stored(client, db_session, seed_section):
    """`computed_status` is earned from facts; the stored column is never the answer."""
    username = entitled(client, "bc8_derived")
    created = create_task(client, username, title="学本节",
                          knowledge_point_name=seed_section["title"])
    master_leaf(client, username, seed_section["leaf"])

    listed = task_in(client.get(PLAN).json()["tasks"], created["id"])
    row = db_session.get(ExamStudyPlanTask, created["id"])
    db_session.expire_all()
    row = db_session.get(ExamStudyPlanTask, created["id"])

    assert listed["computed_status"] == "in_progress"
    assert row.status == "not_started", "the stored column is a create-time stub, not the state"
    # and the response reports the derived value under BOTH keys
    assert listed["status"] == listed["computed_status"]


# ================================================================ B. status write


def test_sending_a_status_field_is_refused_loudly(client):
    """STATUS_UPDATE_SILENTLY_DROPS_FIELD = NO.

    A derived status is not writable, and the contract says so instead of returning 200 and
    doing nothing — which is what it used to do.
    """
    username = entitled(client, "bc8_no_status")
    created = create_task(client, username, title="t")

    for url, payload in (
        (f"{PLAN}/tasks/{created['id']}",
         {"username": username, "subject_key": MODULE, "status": "completed"}),
        (PLAN + "/tasks",
         {"username": username, "subject_key": MODULE, "title": "t2", "status": "completed"}),
        (f"{PLAN}/tasks/{created['id']}",
         {"username": username, "subject_key": MODULE, "status": "done"}),
    ):
        method = client.patch if "/tasks/" in url else client.post
        r = method(url, json=payload)
        assert r.status_code == 422, f"{url} accepted a status field: {r.status_code}"
        assert "status" in r.text, r.text

    # the task survived every refusal, unchanged
    listed = task_in(client.get(PLAN).json()["tasks"], created["id"])
    assert listed["computed_status"] == "not_started"


def test_the_status_enum_is_the_only_one_that_exists():
    from main import ExamPlanTaskStatus
    assert set(ExamPlanTaskStatus.__args__) == {"not_started", "in_progress", "completed"}
    # no invented terminal states
    for invented in ("done", "finished", "mastered", "cancelled"):
        assert invented not in ExamPlanTaskStatus.__args__


# ================================================================ C. no side effects


def test_plan_task_mutation_writes_no_mastery_and_no_wrong_state(client, db_session):
    """PLAN_TASK_COMPLETION_WRITES_MASTERY = 0 and PLAN_TASK_COMPLETION_RESOLVES_WRONG = 0."""
    username = entitled(client, "bc8_side_effect")
    before = plan_snapshot(db_session)

    created = create_task(client, username, title="t")
    client.patch(f"{PLAN}/tasks/{created['id']}",
                 json={"username": username, "subject_key": MODULE, "note": "n",
                       "due_date": "2026-12-01"})
    client.patch(f"{PLAN}/settings",
                 json={"username": username, "subject_key": MODULE, "learning_goal": "目标"})
    client.patch(f"{PLAN}/chapter-practice/1.1",
                 json={"username": username, "subject_key": MODULE, "section_code": "1.1",
                       "section_title": "节", "completed": True})
    client.delete(f"{PLAN}/tasks/{created['id']}")

    db_session.expire_all()
    after = plan_snapshot(db_session)

    assert after[0] == before[0], "tasks created and deleted back to the same count"
    assert after[1] == before[1] + 1, "the section tick is the only row added"
    assert after[2] == before[2], "PLAN_TASK_COMPLETION_WRITES_MASTERY = 0"
    assert after[3] == before[3], "PLAN_TASK_COMPLETION_RESOLVES_WRONG = 0"
    assert after[4] == before[4], "a plan write emits no learning event"


def test_the_canonical_factual_action_is_not_the_plan_route(client, db_session, seed_section):
    """The one thing that DOES move a task's status is the F1C1 knowledge action.

    That is the intended direction: facts move the task, the task never moves the facts.
    """
    username = entitled(client, "bc8_direction")
    created = create_task(client, username, title="学本节",
                          knowledge_point_name=seed_section["title"])
    assert task_in(client.get(PLAN).json()["tasks"], created["id"])["computed_status"] == "not_started"

    knowledge_before = db_session.query(UserKnowledgeProgress).count()
    master_leaf(client, username, seed_section["leaf"])
    db_session.expire_all()

    assert db_session.query(UserKnowledgeProgress).count() > knowledge_before
    assert task_in(client.get(PLAN).json()["tasks"],
                   created["id"])["computed_status"] == "in_progress"


# ================================================================ D. settings shape


def test_settings_read_and_write_share_one_shape(client):
    """The same row must not answer with two different settings payloads."""
    username = entitled(client, "bc8_settings")

    empty = client.get(PLAN).json()["settings"]
    assert empty == {"learning_goal": "", "start_date": "", "daily_hours": "",
                     "weekly_days": 5, "review_strategy": "sequential",
                     "show_completed": True}

    written = client.patch(f"{PLAN}/settings",
                           json={"username": username, "subject_key": MODULE,
                                 "learning_goal": "60 天冲线", "weekly_days": 6}).json()["settings"]
    read = client.get(PLAN).json()["settings"]

    assert written == read
    assert written["learning_goal"] == "60 天冲线"
    assert written["weekly_days"] == 6
    assert written["start_date"] is None, "a stored NULL is not the empty string"


# ================================================================ E. ownership


def test_a_second_user_cannot_read_or_mutate_another_plan(client, db_session):
    owner = entitled(client, "bc8_owner")
    created = create_task(client, owner, title="owner task")

    client.cookies.clear()
    intruder = entitled(client, "bc8_intruder")
    assert client.get(PLAN).json()["tasks"] == []
    assert client.patch(f"{PLAN}/tasks/{created['id']}",
                        json={"username": intruder, "subject_key": MODULE,
                              "note": "hack"}).status_code == 404
    assert client.delete(f"{PLAN}/tasks/{created['id']}").status_code == 404

    db_session.expire_all()
    assert db_session.get(ExamStudyPlanTask, created["id"]) is not None
    assert client.get(PLAN).json()["tasks"] == []


def test_a_body_username_must_match_the_session(client):
    entitled(client, "bc8_identity")
    r = client.post(PLAN + "/tasks",
                    json={"username": "someone_else", "subject_key": MODULE, "title": "t",
                          "scope_type": "all"})
    assert r.status_code in (401, 403), r.status_code


def test_tasks_do_not_leak_across_modules(client):
    username = entitled(client, "bc8_modules")
    create_task(client, username, title="os task")
    assert len(client.get(PLAN).json()["tasks"]) == 1
    for other in ("data_structure", "computer_organization", "computer_network"):
        body = client.get(f"/exam/11408/subjects/{other}/study-plan").json()
        assert body["tasks"] == [], other


# ================================================================ F. entitlement


def test_base_plan_entitlement_policy_is_preserved(client):
    """BASE_PLAN_ENTITLEMENT_POLICY_PRESERVED = PASS.

    The CS408 Study Plan workspace is a PAID product surface, and that policy is deliberately
    unchanged: the whole exam study-plan surface, including the read, stays behind
    `exam_11408.learning_plan`, and the F1C1 knowledge write stays behind it too.

    BC8's original §13 asked for a free base loop and was formally superseded by that later
    product decision, so `FREE_BASE_PLAN_LOOP` is NOT_REQUIRED rather than failed. Pinned
    here so the policy is visible in the code and a future change to it has to be
    deliberate: F1C5 renders its locked/upgrade state from this entitlement instead of a
    free workspace.
    """
    register_and_login(client, "bc8_free")
    r = client.get(PLAN)
    assert r.status_code == 403
    # ACCEL_PRODUCT_S10: the refusal names the UNIFIED TIER that grants the feature and the
    # capability that decides it — no legacy plan code reaches the client.
    assert r.json()["detail"] == {
        "code": "FEATURE_REQUIRES_UPGRADE", "feature": "learning_plan",
        "service_key": "exam_11408", "current_tier": "free",
        "required_tier": "standard", "required_capability": "planning.generate"}
    assert client.post(PLAN + "/tasks",
                       json={"username": "bc8_free", "subject_key": MODULE,
                             "title": "t", "scope_type": "all"}).status_code == 403
    assert client.get(SUMMARY).status_code == 403
    # the F1C1 knowledge write is part of the same paid surface — not ungated by BC8
    assert client.patch(f"{KNOWLEDGE_ITEM}/1.1.1",
                        json={"username": "bc8_free", "subject_key": MODULE,
                              "course_id": f"{MODULE}_11408",
                              "knowledge_point_code": "1.1.1",
                              "status": "mastered"}).status_code == 403

    # the catalog is untouched — the membership UI keeps advertising it, and that is now
    # exactly what the routes enforce
    ent = client.get("/membership/entitlements?service_key=exam_11408").json()
    assert ent["current_tier"] == "free"
    assert ent["features"]["learning_plan"] == {
        "allowed": False, "required_tier": "standard",
        "required_capability": "planning.generate"}

    # a paid user gets the whole surface — the entitlement is a gate, not a removal
    grant_exam_plan("bc8_free")
    assert client.post("/login", json={"username": "bc8_free",
                                       "password": "secret123"}).status_code == 200
    assert client.get(PLAN).status_code == 200


def test_base_plan_operations_never_need_an_ai_provider(client, seed_section):
    """The base loop is authorized without touching the AI capability path."""
    username = entitled(client, "bc8_no_ai")
    created = create_task(client, username, title="t")
    master_leaf(client, username, seed_section["leaf"])
    client.patch(f"{PLAN}/settings", json={"username": username, "subject_key": MODULE})
    assert task_in(client.get(PLAN).json()["tasks"],
                   created["id"])["computed_status"] == "in_progress"


# ================================================================ G. AI boundary


def test_planning_generate_is_a_separate_authorized_capability(client):
    """Free is denied the capability; Standard is allowed it. Separate from `learning_plan`."""
    assert not capabilities.tier_allows("free", "planning.generate")
    assert capabilities.tier_allows("standard", "planning.generate")
    assert capabilities.tier_allows("advanced", "planning.generate")

    register_and_login(client, "bc8_cap_free")
    r = client.post("/learning/plans/generate-preview",
                    json={"username": "bc8_cap_free", "course_id": f"{MODULE}_11408",
                          "days": 3, "goal": "g", "daily_minutes": 60})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == "AI capability unavailable"

    # a paid Exam plan does NOT imply the AI capability, and vice versa
    grant_exam_plan("bc8_cap_free")
    set_tier("bc8_cap_free", "free")
    assert client.post("/learning/plans/generate-preview",
                       json={"username": "bc8_cap_free", "course_id": f"{MODULE}_11408",
                             "days": 3, "goal": "g", "daily_minutes": 60}).status_code == 403


def test_ai_generation_failure_isolates_the_existing_plan(client, db_session, provider_double):
    """PLANNING_GENERATE_FAILURE_ISOLATED = PASS.

    The provider double fails INSIDE the gateway, so the real permission → router →
    estimate → reserve → gateway → settle lifecycle runs and only the outbound call is
    replaced. Nothing here can reach a network.
    """
    username = entitled(client, "bc8_ai_fail")
    set_tier(username, "standard")
    created = create_task(client, username, title="既有任务", due_date="2026-12-01")
    client.patch(f"{PLAN}/chapter-practice/1.1",
                 json={"username": username, "subject_key": MODULE, "section_code": "1.1",
                       "section_title": "节", "completed": True})
    db_session.expire_all()
    before = learner_fact_snapshot(db_session)

    provider_double(behavior="raise_timeout")
    r = client.post("/learning/plans/generate-preview",
                    json={"username": username, "course_id": f"{MODULE}_11408",
                          "days": 3, "goal": "g", "daily_minutes": 60})
    # A provider failure is reported as a failure, not dressed up as a generated plan.
    assert r.status_code == 502, r.text

    db_session.expire_all()
    assert learner_fact_snapshot(db_session) == before
    listed = task_in(client.get(PLAN).json()["tasks"], created["id"])
    assert listed["title"] == "既有任务"
    assert listed["due_date"] == "2026-12-01"


def test_ai_generation_degradation_isolates_the_existing_plan(client, db_session, monkeypatch):
    """The other failure class: an unexpected error inside the preview falls back to a
    deterministic plan instead of failing the request — and still writes no learner fact."""
    username = entitled(client, "bc8_ai_degrade")
    set_tier(username, "standard")
    created = create_task(client, username, title="既有任务")
    db_session.expire_all()
    before = learner_fact_snapshot(db_session)

    monkeypatch.setattr(main, "_scoped_ai_content", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("unexpected failure above the gateway")))
    r = client.post("/learning/plans/generate-preview",
                    json={"username": username, "course_id": f"{MODULE}_11408",
                          "days": 3, "goal": "g", "daily_minutes": 60})
    assert r.status_code == 200, r.text
    assert r.json()["fallback_used"] is True
    assert r.json()["items"], "the fallback still produces a usable suggestion"

    db_session.expire_all()
    assert learner_fact_snapshot(db_session) == before
    assert task_in(client.get(PLAN).json()["tasks"], created["id"])["title"] == "既有任务"


def test_plan_generation_writes_no_learner_fact(client, db_session, provider_double):
    """PLANNING_GENERATE_WRITES_LEARNER_FACT = 0.

    A real generation runs the whole unified AI boundary. The only durable traces it may
    leave are AI AUDIT records — an `ai_request` row and an `ai_called` event. No task, no
    knowledge progress, no mastery, no wrong-answer state.
    """
    username = entitled(client, "bc8_ai_preview")
    set_tier(username, "standard")
    db_session.expire_all()
    before = learner_fact_snapshot(db_session)
    ai_requests_before = db_session.query(AIRequest).count()
    events_before = db_session.query(LearningEvent).count()

    provider_double()
    r = client.post("/learning/plans/generate-preview",
                    json={"username": username, "course_id": f"{MODULE}_11408",
                          "days": 3, "goal": "g", "daily_minutes": 60})
    assert r.status_code == 200, r.text
    assert r.json()["items"], "the preview must return items, even if only the fallback's"

    db_session.expire_all()
    assert learner_fact_snapshot(db_session) == before, "no learner fact may be written"

    # what it MAY leave: durable AI audit, and only that
    assert db_session.query(AIRequest).count() == ai_requests_before + 1
    new_events = (db_session.query(LearningEvent)
                  .order_by(LearningEvent.occurred_at.desc()).limit(1).all())
    assert db_session.query(LearningEvent).count() == events_before + 1
    assert new_events[0].event_type == "ai_called"
    assert new_events[0].source_item_key == "planning.generate"


# ================================================================ H. today_plan


def test_today_plan_is_not_a_calendar_day_boundary(client):
    """TODAY_PLAN_IS_TRUE_DAY_BOUNDARY = NO — pinned so nobody reinterprets it.

    `today_plan` is the three most recently created tasks for the subject. It carries no
    date predicate at all, which is why F1C5 must not render it as 今天.
    """
    username = entitled(client, "bc8_today")
    ancient = create_task(client, username, title="六年前就该做的", due_date="2020-01-01")
    undated = create_task(client, username, title="没有日期")

    today_plan = client.get(DASHBOARD).json()["today_plan"]
    ids = {t["id"] for t in today_plan}
    assert ancient["id"] in ids, "an overdue task is still returned as today's plan"
    assert undated["id"] in ids, "a task with no date is still returned as today's plan"
    assert len(ids) <= 3, "the cap is three newest, not a day"
    due_dates = {t["id"]: t["due_date"] for t in today_plan}
    assert due_dates[ancient["id"]] == "2020-01-01", "the factual date is carried through"


def test_overdue_ordering_comes_from_the_backend(client):
    """The backend owns the only date comparison there is: due_date < today, server-local."""
    username = entitled(client, "bc8_urgency")
    create_task(client, username, title="无期限")
    overdue = create_task(client, username, title="逾期", due_date="2020-01-01")
    future = create_task(client, username, title="将来", due_date="2099-01-01")

    order = [t["id"] for t in client.get(SUMMARY).json()["tasks"]]
    assert order[0] == overdue["id"], "overdue first"
    assert order.index(future["id"]) < order.index(
        next(t["id"] for t in client.get(SUMMARY).json()["tasks"] if t["title"] == "无期限"))


# ================================================================ I. OpenAPI


def test_the_required_plan_surface_is_concretely_typed(client):
    """PLAN_REQUIRED_REQUEST_UNKNOWN = 0 and PLAN_REQUIRED_SUCCESS_UNKNOWN = 0."""
    spec = client.get("/openapi.json").json()
    required = [
        ("get", "/exam/11408/subjects/{subject_key}/study-plan",
         "ExamStudyPlanResponse"),
        ("post", "/exam/11408/subjects/{subject_key}/study-plan/tasks",
         "ExamStudyPlanTaskMutationResponse"),
        ("patch", "/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}",
         "ExamStudyPlanTaskMutationResponse"),
        ("delete", "/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}",
         "ExamStudyPlanTaskDeleteResponse"),
        ("patch", "/exam/11408/subjects/{subject_key}/study-plan/settings",
         "ExamStudyPlanSettingsMutationResponse"),
        ("patch",
         "/exam/11408/subjects/{subject_key}/study-plan/chapter-practice/{node_code}",
         "ExamStudyPlanChapterPracticeResponse"),
    ]
    for method, path, model in required:
        op = spec["paths"][path][method]
        schema = op["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema.get("$ref") == f"#/components/schemas/{model}", (method, path, schema)
        if method in ("post", "patch"):
            assert "requestBody" in op, (method, path)

    item = spec["components"]["schemas"]["ExamStudyPlanTaskItem"]
    assert item["properties"]["computed_status"]["enum"] == [
        "not_started", "in_progress", "completed"]
    assert item["properties"]["action_target"]["enum"] == ["knowledge_map", "practice_center"]
    assert "computed_status" in item["required"]

    # a status field cannot even be expressed in the request contract
    for model in ("ExamStudyPlanTaskCreate", "ExamStudyPlanTaskUpdate"):
        props = spec["components"]["schemas"][model]["properties"]
        assert "status" not in props, model
        assert spec["components"]["schemas"][model]["additionalProperties"] is False, model


def test_the_optional_summary_surfaces_are_typed_too(client):
    spec = client.get("/openapi.json").json()
    assert spec["paths"]["/exam/11408/study-plan/tasks/summary"]["get"]["responses"]["200"][
        "content"]["application/json"]["schema"]["$ref"].endswith(
        "ExamStudyPlanTasksSummaryResponse")
    assert spec["paths"]["/exam/11408/study-plan/summary"]["get"]["responses"]["200"][
        "content"]["application/json"]["schema"]["$ref"].endswith(
        "ExamStudyPlanSubjectsSummaryResponse")


# ================================================================ J. real DB safety


def test_real_app_db_is_never_mutated_by_this_suite():
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        tables = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        rows = con.execute("SELECT COUNT(*) FROM exam_study_plan_tasks").fetchone()[0]
    finally:
        con.close()
    assert integrity == "ok"
    assert tables == 72, "the deployed baseline table count is unchanged"
    assert rows == 0


def test_no_schema_or_migration_was_needed():
    """BC8 is a contract closure: it contributed no revision of its own.

    Stated as a property of BC8's own place in the chain rather than as "the head is
    0009": a later sprint may legitimately advance the head, and that must not be
    mistaken for BC8 having needed a migration. What this pins is that 0009 sits DIRECTLY
    on BC7's 0008 — nothing was inserted between them.
    """
    versions = {p.name: p.read_text(encoding="utf-8")
                for p in (BACKEND_DIR.parent / "migrations" / "versions").glob("*.py")}
    assert any(n.startswith("20260919_0009") for n in versions), sorted(versions)
    bc7_head = next(t for n, t in versions.items() if n.startswith("20260919_0009"))
    assert 'down_revision: Union[str, None] = "20260917_0008"' in bc7_head
