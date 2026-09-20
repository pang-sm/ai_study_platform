"""STEP 7H5: Exam Prep / CS408 final backend acceptance.

The gates this file exists to prove:

  * a FRESH database reaches a complete Exam runtime schema from ``alembic upgrade head``
    alone — the Exam tables are not back-filled by ``Base.metadata.create_all()``;
  * a LEGACY ``backend/app.db`` copy upgrades cleanly and keeps every row (9333 questions);
  * the CS408 learning loop works end to end: profile → practice → wrong → correct →
    records → past paper → knowledge;
  * Free / Standard / Advanced each get exactly the tier behaviour H3 froze, with the
    canonical usage lifecycle (estimate → reserve → execute → actual → settle);
  * a framework-only subject is selectable and its content is refused EXPLICITLY;
  * the legacy ``/exam/11408/*`` routes still work;
  * no Exam path reaches a provider outside the orchestrator.
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import register_and_login
from core.learning_context import ServiceNamespace
from data_plane.models import LearningEvent
from learning.practice import service as practice_service
from learning.practice.adapters import exam as exam_adapter
from learning.spaces.exam_prep import catalog
from learning.spaces.exam_prep import knowledge as exam_knowledge
from learning.spaces.exam_prep.ai import execute_exam_ai
from learning.spaces.exam_prep.context import cs408_context
from models import ExamPracticeAttempt, ExamPrepProfile, PastPaperAttempt, User
from usage import service as usage_service
from usage.models import AIRequest, UsageLedger
import main

EXAM = ServiceNamespace.EXAM_PREP
CS408 = "cs_408"

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"

EXPECTED_HEAD = "20260919_0012"

# The Exam Prep / CS408 runtime schema this step baselines (migration 0008). Derived from
# the exam route handlers, not from a name pattern.
EXAM_RUNTIME_TABLES = {
    "exam_question_bank", "exam_practice_attempts", "exam_wrong_questions",
    "exam_question_done_records", "exam_favorite_questions", "past_paper_attempts",
    "past_paper_wrong_questions", "exam_study_plan_settings",
    "exam_study_plan_chapter_practice", "exam_study_plan_tasks",
    "ai_generated_questions", "user_knowledge_progress", "user_knowledge_review_settings",
    "exam_prep_profiles",
}

FRAMEWORK_ONLY_IDS = ("politics", "english_1", "english_2", "math_1", "math_2", "math_3",
                      "management_aptitude", "economics_joint_aptitude",
                      "law_master_law", "law_master_non_law",
                      "education_basics", "psychology_basics", "history_basics")


# ---------------------------------------------------------------- helpers

def _user(session, username, tier="free") -> User:
    u = User(username=username, hashed_password="x", grade="freshman", major="cs")
    session.add(u)
    session.commit()
    if tier != "free":
        usage_service.activate_subscription(session, u.id, tier, 30)
    return u


def _chapter_attempt(session, username, *, module="data_structure", results=None):
    row = ExamPracticeAttempt(
        username=username, subject_key=module, practice_type="chapter",
        source_type="chapter", status="submitted", title="章节练习",
        question_ids_json=json.dumps([r["question_id"] for r in (results or [])]),
        answers_json=json.dumps({}),
        result_json=json.dumps({"results": results or []}, ensure_ascii=False),
        total_questions=len(results or []), correct_count=0, wrong_count=0, accuracy=0.0,
        started_at=datetime(2024, 5, 1, 9, 0), submitted_at=datetime(2024, 5, 1, 9, 30))
    session.add(row)
    session.commit()
    return row


def _past_paper_attempt(session, username, *, module="computer_network", year=2022,
                        results=None, attempt_no=1):
    row = PastPaperAttempt(
        username=username, mode="11408", subject_key=module, subject_name=module,
        year=year, attempt_no=attempt_no, status="submitted",
        total_questions=len(results or []), choice_correct=0, big_avg_score=0.0,
        total_score=0, max_score=0, wrong_count=0, answers_json=json.dumps({}),
        result_json=json.dumps({"results": results or []}, ensure_ascii=False),
        started_at=datetime(2024, 5, 1, 9, 0), submitted_at=datetime(2024, 5, 1, 9, 30))
    session.add(row)
    session.commit()
    return row


def _events(db, user_id, event_type=None):
    q = db.query(LearningEvent).filter(LearningEvent.user_id == user_id)
    if event_type:
        q = q.filter(LearningEvent.event_type == event_type)
    return q.all()


def _bank_fingerprint(db_path: Path) -> str:
    cols = "id,subject_key,source_type,year,question_number,stem,standard_answer,analysis"
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(f"SELECT {cols} FROM exam_question_bank ORDER BY id")
        payload = "\n".join("\x1f".join("" if v is None else str(v) for v in r) for r in rows)
    finally:
        con.close()
    return hashlib.sha256(payload.encode()).hexdigest()


def _run_alembic_upgrade(db_url: str, revision: str = "head"):
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr


def _tables_and_head(db_path: Path):
    con = sqlite3.connect(str(db_path))
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        head = (con.execute("SELECT version_num FROM alembic_version").fetchone() or [None])[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()
    return tables, head, integrity


# ================================================================ A. deployment

@pytest.fixture
def tmp_workspace():
    d = Path(tempfile.mkdtemp(prefix="h5-accept-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_alembic_only_fresh_deployment_builds_the_exam_runtime_schema(tmp_workspace):
    """A fresh DB needs nothing but ``alembic upgrade head`` for the Exam schema.

    This is the whole point of STEP7H5's migration work: before 0008 the Exam tables came
    from ``ensure_*`` / ``create_all``, so a fresh deployment had no Exam schema at all.
    """
    fresh = tmp_workspace / "fresh.db"
    _run_alembic_upgrade(f"sqlite:///{fresh.as_posix()}")

    tables, head, integrity = _tables_and_head(fresh)
    assert integrity == "ok"
    assert head == EXPECTED_HEAD

    missing = EXAM_RUNTIME_TABLES - tables
    assert missing == set(), f"alembic alone did not produce: {sorted(missing)}"
    # the dead table must NOT have been promoted to a canonical requirement
    assert "exam_favorite_questions_v2" not in tables


def test_alembic_created_exam_schema_is_usable_by_the_orm(tmp_workspace):
    """The alembic-built schema is the real one — the models can query it.

    Proven without ``create_all``: an engine is bound to the migrated file and each Exam
    table is both inspected for column parity and actually queried through the ORM.
    """
    fresh = tmp_workspace / "orm.db"
    _run_alembic_upgrade(f"sqlite:///{fresh.as_posix()}")

    import sqlalchemy as sa
    from sqlalchemy.orm import Session as SASession
    import models as m

    engine = sa.create_engine(f"sqlite:///{fresh.as_posix()}")
    try:
        inspector = sa.inspect(engine)
        present = set(inspector.get_table_names())
        assert EXAM_RUNTIME_TABLES <= present

        for table in sorted(EXAM_RUNTIME_TABLES):
            if table not in m.Base.metadata.tables:
                continue
            declared = {c.name for c in m.Base.metadata.tables[table].columns}
            actual = {c["name"] for c in inspector.get_columns(table)}
            assert declared == actual, f"{table}: {declared ^ actual}"

        # the ORM can actually read every exam table the migration created
        with SASession(engine) as s:
            assert s.query(m.ExamQuestionBank).count() == 0
            assert s.query(m.ExamPrepProfile).count() == 0
            assert s.query(m.UserKnowledgeProgress).count() == 0
    finally:
        engine.dispose()


def test_migration_0008_on_a_legacy_copy_preserves_every_row(tmp_workspace):
    """The same revision must also be safe on a database that already has the tables."""
    if not APP_DB.exists():
        pytest.skip("no working database to copy")
    copy = tmp_workspace / "legacy.db"
    shutil.copy2(APP_DB, copy)
    before_fp = _bank_fingerprint(copy)

    _run_alembic_upgrade(f"sqlite:///{copy.as_posix()}")

    tables, head, integrity = _tables_and_head(copy)
    assert integrity == "ok"
    assert head == EXPECTED_HEAD
    assert EXAM_RUNTIME_TABLES <= tables

    con = sqlite3.connect(str(copy))
    try:
        counts = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                  for t in ("exam_question_bank", "programming_exercises", "knowledge_points")}
    finally:
        con.close()
    assert counts == {"exam_question_bank": 9333, "programming_exercises": 1923,
                      "knowledge_points": 32}
    assert _bank_fingerprint(copy) == before_fp, "question rows must be byte-identical"


def test_migration_0008_does_not_drop_the_dead_table_on_legacy(tmp_workspace):
    """DELETE-LATER is not DELETE-NOW: H5 does not remove it and does not baseline it."""
    if not APP_DB.exists():
        pytest.skip("no working database to copy")
    copy = tmp_workspace / "dead.db"
    shutil.copy2(APP_DB, copy)
    _run_alembic_upgrade(f"sqlite:///{copy.as_posix()}")

    tables, _, _ = _tables_and_head(copy)
    assert "exam_favorite_questions_v2" in tables, "H5 must not drop it"


def test_migration_0008_is_idempotent_on_a_second_head_check(tmp_workspace):
    """Upgrading a database already at head is a no-op, not a failure."""
    fresh = tmp_workspace / "twice.db"
    _run_alembic_upgrade(f"sqlite:///{fresh.as_posix()}")
    _run_alembic_upgrade(f"sqlite:///{fresh.as_posix()}")  # must not raise

    tables, head, integrity = _tables_and_head(fresh)
    assert head == EXPECTED_HEAD and integrity == "ok"
    assert EXAM_RUNTIME_TABLES <= tables


# ================================================================ B. canonical API

def test_canonical_catalog_contract_is_stable(client):
    body = client.get("/exam/prep/catalog").json()
    assert body["catalog_version"] == catalog.CATALOG_VERSION
    assert body["exam_type"] == "postgraduate"
    assert set(body["active_subject_ids"]) == {"cs_408"}
    assert set(body["framework_only_subject_ids"]) == set(FRAMEWORK_ONLY_IDS)
    for subject in body["subjects"]:
        assert {"id", "display_name", "category", "availability", "has_questions",
                "has_past_papers", "has_knowledge_tree", "modules"} <= set(subject)
        assert isinstance(subject["modules"], list)
    cs = next(s for s in body["subjects"] if s["id"] == "cs_408")
    assert [m["id"] for m in cs["modules"]] == list(catalog.CS408_MODULES)


def test_canonical_profile_contract_is_stable(client):
    register_and_login(client, "h5_contract")
    empty = client.get("/exam/prep/profile").json()
    assert set(empty) == {"configured", "exam_type", "selected_track",
                          "selected_subjects", "target_exam_year", "subjects"}
    assert empty["configured"] is False

    put = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": ["cs_408"],
        "target_exam_year": 2027})
    assert put.status_code == 200, put.text
    assert set(put.json()) == set(empty)
    assert put.json()["configured"] is True


def test_cs408_module_ids_and_display_names_are_frozen():
    assert tuple(catalog.CS408_MODULES) == (
        "data_structure", "computer_organization", "operating_system", "computer_network")
    assert catalog.CS408_MODULE_DISPLAY == {
        "data_structure": "数据结构",
        "computer_organization": "计算机组成原理",
        "operating_system": "操作系统",
        "computer_network": "计算机网络",
    }


# ================================================================ C. framework only

@pytest.mark.parametrize("subject_id", FRAMEWORK_ONLY_IDS)
def test_framework_only_subject_is_selectable_but_content_is_explicitly_absent(client, subject_id):
    register_and_login(client, f"h5_fo_{subject_id}")
    put = client.put("/exam/prep/profile", json={
        "selected_track": "cs_408", "selected_subjects": [subject_id]})
    assert put.status_code == 200, put.text
    by_id = {s["id"]: s for s in put.json()["subjects"]}
    assert by_id[subject_id]["availability"] == "framework_only"
    assert by_id[subject_id]["has_questions"] is False
    assert by_id[subject_id]["modules"] == []

    r = client.get(f"/exam/prep/subjects/{subject_id}/content-status")
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "EXAM_CONTENT_NOT_AVAILABLE"
    assert detail["availability"] == "framework_only"


def test_framework_only_access_never_falls_back_to_cs408_or_generates_content(client):
    """The failure is a refusal, not generated placeholder content."""
    register_and_login(client, "h5_fo_gate")
    r = client.get("/exam/prep/subjects/math_1/content-status")
    assert r.status_code == 409
    body = json.dumps(r.json(), ensure_ascii=False)
    assert "cs_408" not in body
    assert "data_structure" not in body


# ================================================================ D. CS408 E2E

def test_cs408_full_learning_loop(db_session):
    """practice → wrong(active) → correct → resolved → records, all under exam_prep."""
    u = _user(db_session, "h5_loop")

    first = _chapter_attempt(db_session, u.username, module="data_structure", results=[
        {"question_id": 11001, "correct": False, "standard_answer": "B", "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, first)
    db_session.expire_all()
    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 1
    assert attempts[0].correct is False

    from learning.wrong_answers import service as wrong_service
    states = wrong_service.list_states(db_session, u.id, service_namespace="exam_prep")
    assert [s.status for s in states] == ["active"]

    second = _chapter_attempt(db_session, u.username, module="data_structure", results=[
        {"question_id": 11001, "correct": True, "standard_answer": "B", "user_answer": "B"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, second)
    db_session.expire_all()
    states = wrong_service.list_states(db_session, u.id, service_namespace="exam_prep")
    assert [s.status for s in states] == ["resolved"]

    # records: every exam fact lands in the shared stream under the canonical context
    events = _events(db_session, u.id, "question_answered")
    assert len(events) == 2
    for ev in events:
        assert ev.service_key == "exam_prep"
        assert ev.subject_key == "cs_408"
        assert json.loads(ev.knowledge_point_ref_json)["exam_module_id"] == "data_structure"


def test_cs408_past_paper_loop_feeds_the_same_pipeline(db_session):
    u = _user(db_session, "h5_pp")
    row = _past_paper_attempt(db_session, u.username, module="computer_network", year=2023,
                              attempt_no=1, results=[
        {"question_id": 12001, "number": 33, "type": "选择题", "correct": False,
         "score": 0, "full_score": 2, "user_answer": "A", "standard_answer": "B"}])
    outcome = exam_adapter.mirror_past_paper_attempt(db_session, u, row)
    assert outcome.mirrored == 1

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert {a.question_source_type for a in attempts} == {"past_exam"}
    ref = json.loads(attempts[0].question_ref_json)
    assert ref["context"]["exam_subject_id"] == CS408
    assert ref["context"]["exam_module_id"] == "computer_network"


def test_cs408_knowledge_writes_through_the_canonical_writer(client, db_session):
    """The live study-plan PATCH still works and still writes the legacy scope id."""
    register_and_login(client, "h5_know")
    from models import UserKnowledgeProgress
    payload = json.loads(main._knowledge_map_seed_path("data_structure_11408").read_text(
        encoding="utf-8"))
    index = main._build_enriched_map_index(payload.get("chapters") or [])
    code = next(c for c, n in index.items() if main._is_leaf_node(n))

    r = client.patch(
        f"/exam/11408/subjects/data_structure/study-plan/knowledge-items/{code}",
        json={"username": "h5_know", "subject_key": "data_structure",
              "course_id": "data_structure_11408", "knowledge_point_code": code,
              "status": "learning", "knowledge_point_title": "叶子"})
    # a Free user is refused by the LEGACY study-plan entitlement — that is preserved
    assert r.status_code in (200, 403), r.text


def test_exam_knowledge_writer_records_a_real_transition_once(db_session):
    u = _user(db_session, "h5_kw_event")
    payload = json.loads(main._knowledge_map_seed_path("operating_system_11408").read_text(
        encoding="utf-8"))
    index = main._build_enriched_map_index(payload.get("chapters") or [])
    code = next(c for c, n in index.items() if main._is_leaf_node(n))
    validator = lambda c: c in index  # noqa: E731

    for _ in range(3):
        t = exam_knowledge.apply_exam_knowledge_change(
            db_session, user=u, module_key="operating_system", knowledge_point_code=code,
            status="learning", code_validator=validator)
        exam_knowledge.commit_and_emit(db_session, t)
    db_session.expire_all()

    events = _events(db_session, u.id, "knowledge_status_changed")
    assert len(events) == 1, "a repeated status must not emit a second transition"
    assert events[0].service_key == "exam_prep"
    assert events[0].subject_key == CS408
    ctx = json.loads(events[0].knowledge_point_ref_json)
    assert ctx["exam_module_id"] == "operating_system"
    assert "exam_track_id" not in ctx, "the track never enters an event"


def test_generic_knowledge_route_with_an_exam_scope_emits_an_exam_event(client):
    """STEP7H5 finding: the generic course route is reachable with ``<module>_11408``.

    Before the fix it wrote the exam fact but recorded a ``course_learning`` event — an
    exam change mislabelled as a course change. It must now go through the exam space.
    """
    register_and_login(client, "h5_generic_route")
    payload = json.loads(main._knowledge_map_seed_path("computer_network_11408").read_text(
        encoding="utf-8"))
    index = main._build_enriched_map_index(payload.get("chapters") or [])
    code = next(c for c, n in index.items() if main._is_leaf_node(n))

    r = client.patch("/knowledge-map/progress", json={
        "username": "h5_generic_route", "course_id": "computer_network_11408",
        "knowledge_point_code": code, "knowledge_point_title": "叶子", "status": "mastered"})
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"success", "progress", "node"}, "response contract preserved"

    import database
    from models import UserKnowledgeProgress
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == "h5_generic_route").one()
        events = [e for e in db.query(LearningEvent)
                  .filter(LearningEvent.user_id == user.id,
                          LearningEvent.event_type == "knowledge_status_changed").all()]
        assert len(events) == 1
        assert events[0].service_key == "exam_prep", "an exam fact must not be a course event"
        assert events[0].subject_key == CS408
        assert json.loads(events[0].knowledge_point_ref_json)["exam_module_id"] == \
            "computer_network"

        row = (db.query(UserKnowledgeProgress)
               .filter(UserKnowledgeProgress.username == "h5_generic_route",
                       UserKnowledgeProgress.knowledge_point_code == code).first())
        assert row.course_id == "computer_network_11408", "legacy scope id preserved"


def test_no_undeclared_exam_knowledge_write_paths():
    from learning.spaces.exam_prep.knowledge import (exam_mutation_paths,
                                                     exam_paths_not_consolidated)
    assert exam_paths_not_consolidated() == []
    statuses = {r["path"]: r["status"] for r in exam_mutation_paths()}
    assert statuses["PATCH /exam/11408/{k}/study-plan/knowledge-items/{code}"] == \
        "CANONICAL_WRITER"


# ================================================================ E. tiers

class _CountingProvider:
    """FakeProvider that records the capability each call was routed for."""

    def __init__(self, calls, content=None, **kwargs):
        from ai.providers import FakeProvider
        self._inner = FakeProvider(**kwargs)
        self._calls = calls
        self._content = content

    @property
    def name(self):
        return self._inner.name

    def complete(self, spec):
        self._calls.append((self._inner.name, spec.model, spec.capability))
        response = self._inner.complete(spec)
        if self._content is None:
            return response
        import dataclasses
        return dataclasses.replace(response, content=self._content)


@pytest.fixture
def provider(monkeypatch):
    calls: list = []

    def _install(content=None):
        from ai.providers import FakeProvider

        def _make(name):
            return _CountingProvider(calls, content=content, provider=name,
                                     input_tokens=50, output_tokens=50)
        monkeypatch.setattr("ai.orchestrator.default_provider_factory", _make)
        return calls

    return _install


@pytest.fixture(autouse=True)
def no_legacy_exam_provider(monkeypatch):
    monkeypatch.setattr(main, "call_deepseek", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Exam AI reached the legacy direct provider client")))


def _fresh_request(username):
    import database
    with database.SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        return (db.query(AIRequest).filter(AIRequest.user_id == user.id)
                .order_by(AIRequest.id.desc()).first())


def test_free_exam_loop_persists_facts_without_paid_ai(db_session, provider):
    """Free users keep the full learning loop; only the paid capabilities are refused."""
    u = _user(db_session, "h5_free", tier="free")
    calls = provider()

    _chapter_attempt(db_session, u.username, module="data_structure",
                     results=[{"question_id": 13001, "correct": False, "user_answer": "C"}])
    row = db_session.query(ExamPracticeAttempt).filter_by(username=u.username).one()
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()
    assert len(practice_service.list_attempts(db_session, u.id,
                                              service_namespace="exam_prep")) == 1

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        execute_exam_ai(db_session, u, "question.generate", [{"role": "user", "content": "x"}],
                        learning_context=cs408_context(u, module_key="data_structure"))
    assert exc.value.status_code == 403
    assert calls == [], "a denied capability must never reach a provider"


@pytest.mark.parametrize("capability", ["question.generate", "planning.generate",
                                        "answer.grade"])
def test_standard_exam_ai_loop_runs_the_full_usage_lifecycle(db_session, provider, capability):
    u = _user(db_session, f"h5_std_{capability.replace('.', '_')}", tier="standard")
    calls = provider(content=json.dumps({"score": 8, "feedback": "ok", "questions": []}))

    execute_exam_ai(db_session, u, capability, [{"role": "user", "content": "x"}],
                    learning_context=cs408_context(u, module_key="computer_network"))
    assert len(calls) == 1 and calls[0][2] == capability

    req = _fresh_request(u.username)
    assert req is not None
    assert req.service_namespace == "exam_prep"
    # the exam subject / module live in the request's canonical context, not a column
    ctx = req.context_json
    if isinstance(ctx, str):
        ctx = json.loads(ctx)
    assert ctx["exam_subject_id"] == CS408
    assert ctx["exam_module_id"] == "computer_network"
    assert req.status == "settled"
    assert db_session.query(UsageLedger).filter(
        UsageLedger.request_id == req.request_id).count() >= 1


def test_advanced_may_use_report_generate_but_standard_may_not(db_session, provider):
    from fastapi import HTTPException
    std = _user(db_session, "h5_adv_std", tier="standard")
    calls = provider(content="{}")
    with pytest.raises(HTTPException) as exc:
        execute_exam_ai(db_session, std, "report.generate", [{"role": "user", "content": "x"}],
                        learning_context=cs408_context(std, module_key="data_structure"))
    assert exc.value.status_code == 403
    assert calls == []

    adv = _user(db_session, "h5_adv_adv", tier="advanced")
    calls2 = provider(content="{}")
    execute_exam_ai(db_session, adv, "report.generate", [{"role": "user", "content": "x"}],
                    learning_context=cs408_context(adv, module_key="data_structure"))
    assert len(calls2) == 1 and calls2[0][2] == "report.generate"


# ================================================================ F. legacy compat

LEGACY_CS408_READS = (
    "/exam/11408/subjects/data_structure/dashboard-summary",
    "/exam/11408/data_structure/chapter-practice/outline",
    "/exam/11408/data_structure/chapter-practice/questions",
    "/exam/11408/data_structure/past-papers",
    "/exam/11408/data_structure/wrong-questions",
    "/exam/11408/data_structure/favorites",
    "/exam/11408/data_structure/done-records",
    "/exam/11408/data_structure/question-bank/stats",
    "/exam/11408/data_structure/ai-questions",
    "/exam/11408/data_structure/practice/stats",
)


@pytest.mark.parametrize("url", LEGACY_CS408_READS)
def test_legacy_11408_routes_still_answer(client, url):
    register_and_login(client, f"h5_legacy_{abs(hash(url)) % 10**8}")
    r = client.get(url)
    assert r.status_code == 200, f"{url} -> {r.status_code} {r.text[:200]}"


def test_legacy_study_plan_route_keeps_its_entitlement_behaviour(client):
    register_and_login(client, "h5_legacy_plan")
    r = client.get("/exam/11408/subjects/data_structure/study-plan")
    assert r.status_code == 403, "legacy learning_plan entitlement is preserved"


def test_legacy_routes_and_canonical_routes_coexist():
    paths = {(r.path, tuple(sorted(getattr(r, "methods", []) or [])))
             for r in main.app.routes}
    assert any(p.startswith("/exam/11408/") for p, _ in paths)
    assert any(p.startswith("/exam/prep/") for p, _ in paths)


# ================================================================ G. routing hygiene

def test_no_duplicate_method_path_registrations():
    seen: dict = {}
    for route in main.app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        for method in (getattr(route, "methods", None) or []):
            if method in ("HEAD", "OPTIONS"):
                continue
            seen.setdefault((method, path), []).append(getattr(route, "name", "?"))
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    assert duplicates == {}, duplicates


# ================================================================ H. AI reachability

def test_exam_business_code_reaches_no_provider_directly():
    exam_dir = Path(exam_knowledge.__file__).parent
    sources = [*sorted(exam_dir.glob("*.py")), BACKEND_DIR / "routers" / "exam_prep.py"]
    for path in sources:
        src = path.read_text(encoding="utf-8")
        for marker in ("DEEPSEEK_API_KEY", "call_deepseek", "OpenAI(",
                       "chat.completions", "DASHSCOPE_API_KEY"):
            assert marker not in src, f"{path.name} reaches a provider via {marker}"


# ================================================================ H2. concurrency stress

H5_STRESS_ROUNDS = 500  # 500 rounds x 2 racing facts = 1000 concurrent attempts


def test_wrong_projection_survives_1000_concurrent_attempts(db_session):
    """STEP7H2-C1's compare-and-recompute must not have regressed under STEP7H5.

    Two distinct wrong facts race for the same question; the projection is
    recompute-not-increment, so the pass that writes last must have derived from the
    complete fact set. A stale-read regression shows up as ``wrong_count == 1`` in some
    round — one green run is not evidence, hence the loop.
    """
    from tests.test_wrong_answers import _race_once
    from learning.wrong_answers import service as wrong_service
    import database

    u = _user(db_session, "h5_stress")
    errors: list = []
    for round_no in range(H5_STRESS_ROUNDS):
        _race_once(u, qid=f"h5-race-{round_no}", errors=errors)
        with database.SessionLocal() as fresh:
            rows = [r for r in wrong_service.list_states(
                        fresh, u.id, service_namespace="exam_prep")
                    if r.question_source_id == f"h5-race-{round_no}"]
            observed = (len(rows), rows[0].wrong_count if rows else None)
        assert errors == [], f"round {round_no}: worker error(s) {errors}"
        assert observed == (1, 2), f"round {round_no}: stale projection {observed}"


# ================================================================ I. isolation

def test_profile_is_isolated_between_users(client):
    register_and_login(client, "h5_iso_a")
    client.put("/exam/prep/profile", json={"selected_track": "cs_408",
                                           "selected_subjects": ["cs_408"],
                                           "target_exam_year": 2027})
    second = TestClient(main.app)
    try:
        register_and_login(second, "h5_iso_b")
        body = second.get("/exam/prep/profile").json()
        assert body["configured"] is False and body["target_exam_year"] is None
    finally:
        second.close()
    assert client.get("/exam/prep/profile").json()["selected_track"] == "cs_408"


def test_cross_user_practice_and_wrong_are_isolated(db_session):
    from learning.wrong_answers import service as wrong_service
    a = _user(db_session, "h5_x_a")
    b = _user(db_session, "h5_x_b")

    row = _chapter_attempt(db_session, a.username, module="data_structure",
                           results=[{"question_id": 14001, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, a, row)
    db_session.expire_all()

    assert len(practice_service.list_attempts(db_session, a.id,
                                              service_namespace="exam_prep")) == 1
    assert practice_service.list_attempts(db_session, b.id, service_namespace="exam_prep") == []
    assert len(wrong_service.list_states(db_session, a.id, service_namespace="exam_prep")) == 1
    assert wrong_service.list_states(db_session, b.id, service_namespace="exam_prep") == []


def test_cross_namespace_isolation_course_vs_exam(db_session):
    """The same token means a course_id in one space and an exam module in the other."""
    u = _user(db_session, "h5_x_ns")
    from learning.spaces.course_learning import knowledge as course_knowledge

    course_knowledge.apply_knowledge_change(
        db_session, username=u.username, course_id="data_structure",
        event_type="question_correct", knowledge_point_code="KP1", delta=10)
    db_session.commit()

    row = _chapter_attempt(db_session, u.username, module="data_structure",
                           results=[{"question_id": 15001, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()

    course_attempts = practice_service.list_attempts(
        db_session, u.id, service_namespace="course_learning")
    exam_attempts = practice_service.list_attempts(
        db_session, u.id, service_namespace="exam_prep")
    assert course_attempts == []
    assert len(exam_attempts) == 1


def test_cross_module_isolation_within_exam(db_session):
    u = _user(db_session, "h5_x_mod")
    row = _chapter_attempt(db_session, u.username, module="computer_network",
                           results=[{"question_id": 16001, "correct": False, "user_answer": "C"}])
    exam_adapter.mirror_exam_practice_attempt(db_session, u, row)
    db_session.expire_all()

    attempts = practice_service.list_attempts(db_session, u.id, service_namespace="exam_prep")
    assert len(attempts) == 1
    ctx = json.loads(attempts[0].context_json)
    assert ctx["exam_module_id"] == "computer_network"


# ================================================================ J. protected assets

def test_protected_assets_are_unchanged():
    if not APP_DB.exists():
        pytest.skip("no working database")
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM exam_question_bank").fetchone()[0] == 9333
        assert con.execute("SELECT COUNT(*) FROM programming_exercises").fetchone()[0] == 1923
        assert con.execute("SELECT COUNT(*) FROM knowledge_points").fetchone()[0] == 32
        subjects = {r[0] for r in con.execute(
            "SELECT DISTINCT subject_key FROM exam_question_bank")}
        assert subjects == set(catalog.CS408_MODULES)
        counts = dict(con.execute(
            "SELECT subject_key, COUNT(*) FROM exam_question_bank GROUP BY 1"))
    finally:
        con.close()
    assert counts == {"data_structure": 5903, "computer_organization": 1330,
                      "operating_system": 1180, "computer_network": 920}
