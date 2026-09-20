"""FRONTEND_BLOCKER_BC7 — CS408 wrong-answer canonicalization.

Gates this file exists to prove:

  * ONE canonical wrong-answer truth. ``wrong_answer_states`` is the owner; the two legacy
    tables are not an authority, not a fallback and not a merge input for the read surface;
  * a question enters the canonical wrong state ONLY when there is a factual submitted
    attempt, a non-empty answer, and an authoritative incorrect judgement. A blank answer
    and a self-review answer enter nothing — on every Exam write path;
  * a later factual correct attempt resolves the state, for chapter practice AND past
    papers, and a repeat wrong updates that one state instead of adding another;
  * the state's schema reaches a deployed database through Alembic, not through
    ``Base.metadata.create_all``;
  * the canonical read surface is typed, module-scoped, paginated, and never exposes
    another learner's state.

Everything here that touches a database builds a TEMP copy. ``backend/app.db`` is only ever
opened read-only.
"""
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
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from conftest import register_and_login
from models import (
    ExamPracticeAttempt,
    ExamQuestionBank,
    ExamWrongQuestion,
    PastPaperWrongQuestion,
    User,
    UserKnowledgeProgress,
)
from learning.wrong_answers import legacy as wrong_legacy
from learning.wrong_answers import service as wrong_service
from learning.wrong_answers.models import WrongAnswerState

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DB = BACKEND_DIR / "app.db"

EXPECTED_HEAD = "20260919_0012"
CANONICAL_TABLE = "wrong_answer_states"
MODULE_COLUMN = "module_key"
MODULE_INDEX = "ix_wrong_answer_states_user_ns_module"

SUBJECT = "computer_organization"
MODULE = "operating_system"
YEAR = 2022


# ---------------------------------------------------------------- helpers


def _run_alembic(db_url: str, revision: str = "head"):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(REPO_ROOT), env={**os.environ, "DATABASE_URL": db_url},
        capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr


def _session_for(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    return engine, sessionmaker(bind=engine)()


def _copy_real_db(directory: Path) -> Path:
    """A writable TEMP copy of the real database. The original is never opened for write."""
    target = directory / "app.db"
    shutil.copy(APP_DB, target)
    return target


def _table_names(db_path: Path) -> set:
    con = sqlite3.connect(str(db_path))
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


@pytest.fixture
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="bc7-"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def chapter_bank(db_session):
    """A deterministic chapter bank: two choice questions and one big question."""
    rows = [
        ExamQuestionBank(subject_key=MODULE, subject_name="操作系统", source_type="chapter",
                         visibility="public", knowledge_point_id="1.1",
                         knowledge_point_name="进程", question_type="choice",
                         stem="BC7 章节选择一", options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="A", analysis="BC7 章节解析一", is_active=True),
        ExamQuestionBank(subject_key=MODULE, subject_name="操作系统", source_type="chapter",
                         visibility="public", knowledge_point_id="1.2",
                         knowledge_point_name="线程", question_type="choice",
                         stem="BC7 章节选择二", options_json=json.dumps({"A": "甲", "B": "乙"}),
                         standard_answer="B", analysis="", is_active=True),
        ExamQuestionBank(subject_key=MODULE, subject_name="操作系统", source_type="chapter",
                         visibility="public", knowledge_point_id="1.3",
                         knowledge_point_name="调度", question_type="big",
                         stem="BC7 章节大题", options_json="{}",
                         standard_answer="BC7 参考答案", analysis="BC7 大题解析", is_active=True),
    ]
    for row in rows:
        db_session.add(row)
    db_session.commit()
    for row in rows:
        db_session.refresh(row)
    ids = [row.id for row in rows]
    try:
        yield {row.stem: row for row in rows}
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def _chapter_flow(client, chapter_ids):
    created = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                          json={"question_ids": chapter_ids})
    assert created.status_code == 200, created.text
    return created.json()["attempt_id"]


def _chapter_submit(client, attempt_id, answers):
    return client.post(
        f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/submit",
        json={"answers": answers})


def _items(client, query=""):
    response = client.get(f"/wrong-answers{query}")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _states(db, user, **kwargs):
    return wrong_service.list_states(db, user.id, service_namespace="exam_prep", **kwargs)


# ================================================================ A. migration


def test_migration_head_carries_the_canonical_wrong_answer_schema(tmp_dir):
    """A fresh DB reaches the canonical wrong-answer schema through Alembic alone."""
    db_path = tmp_dir / "fresh.db"
    _run_alembic(f"sqlite:///{db_path.as_posix()}")

    con = sqlite3.connect(str(db_path))
    try:
        head = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()

    assert head == EXPECTED_HEAD
    assert integrity == "ok"
    assert CANONICAL_TABLE in _table_names(db_path)

    inspector = inspect(create_engine(f"sqlite:///{db_path.as_posix()}"))
    columns = {c["name"]: c for c in inspector.get_columns(CANONICAL_TABLE)}
    assert MODULE_COLUMN in columns
    assert columns[MODULE_COLUMN]["nullable"] is False
    assert MODULE_INDEX in {i["name"] for i in inspector.get_indexes(CANONICAL_TABLE)}


def test_migration_is_additive_and_idempotent_on_a_legacy_copy(tmp_dir):
    """The real legacy schema (72 tables, no alembic_version) migrates without losing a row."""
    db_path = _copy_real_db(tmp_dir)
    before_tables = _table_names(db_path)
    con = sqlite3.connect(str(db_path))
    try:
        bank_before = con.execute("SELECT COUNT(*) FROM exam_question_bank").fetchone()[0]
    finally:
        con.close()

    _run_alembic(f"sqlite:///{db_path.as_posix()}")
    _run_alembic(f"sqlite:///{db_path.as_posix()}")      # second head check: a no-op

    con = sqlite3.connect(str(db_path))
    try:
        head = con.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        bank_after = con.execute("SELECT COUNT(*) FROM exam_question_bank").fetchone()[0]
    finally:
        con.close()

    assert head == EXPECTED_HEAD
    assert integrity == "ok"
    assert bank_after == bank_before == 9333
    assert before_tables <= _table_names(db_path)        # additive only, nothing dropped
    assert CANONICAL_TABLE in _table_names(db_path)


def test_wrong_answer_subsystem_does_not_need_create_all(tmp_dir):
    """A migrated legacy copy serves the canonical surface with ``create_all`` disabled.

    This is the gate ``WRONG_STATE_REQUIRES_CREATE_ALL_TO_EXIST = NO``: if the runtime only
    worked because ``Base.metadata.create_all`` silently built an unapplied table, disabling
    it would break the wrong-answer path. It does not.
    """
    db_path = _copy_real_db(tmp_dir)
    _run_alembic(f"sqlite:///{db_path.as_posix()}")
    assert CANONICAL_TABLE in _table_names(db_path)

    script = """
import json, sqlalchemy
sqlalchemy.schema.MetaData.create_all = lambda self, *a, **k: None   # no runtime DDL
from unittest.mock import patch
import main
codes = []
def _capture(_recipient, code):
    codes.append(code)
    return True
with patch.object(main, "_send_email_code", side_effect=_capture):
    main._send_email_code("x@example.test", "000000")
from fastapi.testclient import TestClient
with TestClient(main.app) as client:
    with patch.object(main, "_send_email_code", side_effect=_capture):
        client.post("/auth/register/send-code", json={"email": "bc7@example.test"})
        client.post("/auth/register/verify-code",
                    json={"email": "bc7@example.test", "code": codes[-1]})
    assert client.post("/register", json={"username": "bc7_no_create_all",
                                          "password": "secret123",
                                          "email": "bc7@example.test"}).status_code == 200
    assert client.post("/login", json={"username": "bc7_no_create_all",
                                       "password": "secret123"}).status_code == 200
    sid = client.post("/practice/sessions",
                      json={"service_namespace": "exam_prep"}).json()["id"]
    r = client.post(f"/practice/sessions/{sid}/attempts",
                    json={"question_source_type": "static_question_bank",
                          "question_source_id": "31415", "answer": "A", "correct": False})
    assert r.status_code == 200, r.text
    body = client.get("/wrong-answers?service_namespace=exam_prep").json()
    assert body["total"] == 1, body
    assert body["items"][0]["status"] == "active"
print("CREATE_ALL_INDEPENDENT_OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=str(BACKEND_DIR),
        env={**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
             "UPLOAD_ROOT": str(tmp_dir / "uploads")},
        capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CREATE_ALL_INDEPENDENT_OK" in result.stdout


# ================================================================ B. backfill


def test_legacy_backfill_excludes_blanks_and_collapses_duplicates(tmp_dir):
    """The historical import over a POLLUTED legacy copy, measured end to end.

    The real database holds zero wrong rows, so the interesting cases are injected into a
    TEMP copy: an unanswered row, and the same past-paper question recorded twice.
    """
    db_path = _copy_real_db(tmp_dir)
    _run_alembic(f"sqlite:///{db_path.as_posix()}")

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("INSERT INTO users (username, hashed_password, grade, major, created_at) "
                    "VALUES ('bc7_legacy', 'x', 'freshman', 'cs', '2024-01-01 00:00:00')")
        con.execute(
            "INSERT INTO exam_wrong_questions (username, subject_key, question_bank_id, "
            "question_type, user_answer, status, mastered, review_count, created_at) "
            "VALUES ('bc7_legacy', ?, 5101, '选择题', 'B', 'active', 0, 1, '2024-01-01 00:00:00')",
            (MODULE,))
        # The blank the old grader filed as 答错.
        con.execute(
            "INSERT INTO exam_wrong_questions (username, subject_key, question_bank_id, "
            "question_type, user_answer, status, mastered, review_count, created_at) "
            "VALUES ('bc7_legacy', ?, 5102, '选择题', '', 'active', 0, 0, '2024-01-01 00:00:00')",
            (MODULE,))
        # The same past-paper question, filed twice by two sittings of the paper.
        for _ in range(2):
            con.execute(
                "INSERT INTO past_paper_wrong_questions (username, subject_key, source, year, "
                "question_id, question_number, question_type, user_answer, status, mastered, "
                "created_at) VALUES ('bc7_legacy', ?, 'past_paper', 2022, '5103', 33, "
                "'选择题', 'C', 'active', 0, '2024-01-01 00:00:00')", (MODULE,))
        con.commit()
    finally:
        con.close()

    engine, session = _session_for(db_path)
    try:
        report = wrong_legacy.run_legacy_wrong_backfill(session)
        rows = session.query(WrongAnswerState).all()
        states = {(r.question_source_type, r.question_source_id): r for r in rows}
    finally:
        session.close()
        engine.dispose()

    assert report["legacy_blank_rows"] == 1
    assert report["legacy_duplicate_rows"] == 1
    assert len(rows) == 2, "three legacy rows collapse into two canonical states"
    assert states[("static_question_bank", "5101")].status == "active"
    assert states[("static_question_bank", "5101")].module_key == MODULE
    assert ("static_question_bank", "5102") not in states, "a blank never becomes canonical"
    duplicate = states[("past_exam", "5103")]
    assert duplicate.wrong_count == 2, "the duplicate is collapsed, not copied"
    assert duplicate.module_key == MODULE

    engine, session = _session_for(db_path)
    try:
        wrong_legacy.run_legacy_wrong_backfill(session)      # re-run: idempotent
        assert session.query(WrongAnswerState).count() == 2
    finally:
        session.close()
        engine.dispose()


# ================================================================ C. write semantics


def test_chapter_wrong_repeat_wrong_then_correct(client, db_session, chapter_bank):
    """The chapter runtime matrix: active → still ONE row on a repeat → resolved on a retry."""
    register_and_login(client, "bc7_chapter")
    user = db_session.query(User).filter(User.username == "bc7_chapter").first()
    qid = chapter_bank["BC7 章节选择一"].id

    first = _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})
    assert first.status_code == 200, first.text
    states = _states(db_session, user)
    assert len(states) == 1 and states[0].status == "active"
    assert states[0].wrong_count == 1
    assert states[0].module_key == MODULE

    second = _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})
    assert second.status_code == 200
    db_session.expire_all()
    states = _states(db_session, user)
    assert len(states) == 1, "a repeat wrong must not add a second canonical row"
    assert states[0].wrong_count == 2
    assert states[0].status == "active"

    third = _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "A"})
    assert third.status_code == 200
    db_session.expire_all()
    states = _states(db_session, user)
    assert len(states) == 1
    assert states[0].status == "resolved"
    assert states[0].resolved_at is not None


def test_chapter_blank_and_self_review_write_no_wrong_state(client, db_session, chapter_bank):
    """UNANSWERED != INCORRECT, and an ungraded subjective answer is not a wrong answer."""
    register_and_login(client, "bc7_chapter_blank")
    user = db_session.query(User).filter(User.username == "bc7_chapter_blank").first()
    choice = chapter_bank["BC7 章节选择一"].id
    big = chapter_bank["BC7 章节大题"].id

    blank = _chapter_submit(client, _chapter_flow(client, [choice, big]), {"attempt": "x"})
    assert blank.status_code == 200, blank.text
    body = blank.json()
    assert body["wrong_count"] == 0
    assert body["correct_count"] == 0
    assert body["results"][0]["correct"] is None, "a blank carries no verdict"
    assert body["results"][1]["judge"] == "self_review"
    assert wrong_service.list_states(db_session, user.id) == []
    assert db_session.query(ExamWrongQuestion).filter(
        ExamWrongQuestion.username == "bc7_chapter_blank").count() == 0, (
        "the legacy writer is fixed too, not just the canonical projection")


def test_past_paper_wrong_repeat_correct_and_blank(client, db_session):
    """The past-paper runtime matrix, including the re-sit that used to duplicate rows."""
    register_and_login(client, "bc7_past")
    user = db_session.query(User).filter(User.username == "bc7_past").first()
    rows = [
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理",
                         source_type="past_paper", visibility="public", year=YEAR,
                         question_number=701, question_type="choice", stem="BC7 真题一",
                         options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="A",
                         is_active=True, source_ref="past_paper:2022-Q701"),
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理",
                         source_type="past_paper", visibility="public", year=YEAR,
                         question_number=702, question_type="choice", stem="BC7 真题二",
                         options_json=json.dumps({"A": "甲", "B": "乙"}), standard_answer="B",
                         is_active=True, source_ref="past_paper:2022-Q702"),
        ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理",
                         source_type="past_paper", visibility="public", year=YEAR,
                         question_number=703, question_type="big", stem="BC7 真题大题",
                         options_json="{}", standard_answer="BC7 真题答案",
                         is_active=True, source_ref="past_paper:2022-Q703"),
    ]

    def _sit(answers):
        created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts",
                              json={"year": YEAR})
        assert created.status_code == 200, created.text
        attempt_id = created.json()["attempt_id"]
        submitted = client.post(
            f"/exam/11408/{SUBJECT}/past-paper-attempts/{attempt_id}/submit",
            json={"answers": answers})
        assert submitted.status_code == 200, submitted.text
        return submitted.json()

    for row in rows:
        db_session.add(row)
    db_session.commit()
    ids = [row.id for row in rows]
    try:
        first = _sit({"701": "B", "702": "B", "703": "我的作答"})
        assert first["choice_correct"] == 1, "702 was answered correctly"
        assert first["self_review_count"] == 1
        states = _states(db_session, user)
        assert len(states) == 1, "only the answered-and-wrong 701 is wrong"
        assert states[0].status == "active"
        assert states[0].module_key == SUBJECT
        assert states[0].wrong_count == 1

        _sit({"701": "B"})                     # re-sit: 702 and 703 left blank
        db_session.expire_all()
        states = _states(db_session, user)
        assert len(states) == 1, "re-sitting must not duplicate the canonical state"
        assert states[0].wrong_count == 2

        _sit({"701": "A"})                     # correct retry resolves
        db_session.expire_all()
        states = _states(db_session, user)
        assert len(states) == 1
        assert states[0].status == "resolved"
        assert states[0].resolved_at is not None
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.query(PastPaperWrongQuestion).filter(
            PastPaperWrongQuestion.year == YEAR,
            PastPaperWrongQuestion.subject_key == SUBJECT).delete(synchronize_session=False)
        db_session.commit()


def test_blank_writes_nothing_on_the_legacy_tables_either(client, db_session, chapter_bank):
    """The fix is in the write path, not a read filter: the legacy writer is fixed too."""
    register_and_login(client, "bc7_legacy_write")
    choice = chapter_bank["BC7 章节选择一"].id
    _chapter_submit(client, _chapter_flow(client, [choice]), {"answers": {}})
    assert db_session.query(ExamWrongQuestion).filter(
        ExamWrongQuestion.username == "bc7_legacy_write").count() == 0


# ================================================================ D. read surface


def test_record_carries_public_identity_and_never_internal_ids(client, db_session):
    register_and_login(client, "bc7_identity")
    rows = [ExamQuestionBank(subject_key=SUBJECT, subject_name="计算机组成原理",
                             source_type="past_paper", visibility="public", year=YEAR,
                             question_number=711, question_type="choice", stem="BC7 身份题",
                             options_json=json.dumps({"A": "甲", "B": "乙"}),
                             standard_answer="A", analysis="BC7 身份解析", is_active=True,
                             source_ref="past_paper:2022-Q711")]
    for row in rows:
        db_session.add(row)
    db_session.commit()
    ids = [row.id for row in rows]
    try:
        created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts",
                              json={"year": YEAR}).json()
        client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts/"
                    f"{created['attempt_id']}/submit", json={"answers": {"711": "B"}})

        record = _items(client)[0]
        assert record["source_kind"] == "past_paper"
        assert record["source_label"] == "历年真题"
        assert record["module_key"] == SUBJECT
        assert record["module_name"] == "计算机组成原理"
        assert record["year"] == YEAR and record["question_number"] == 711
        assert record["stem"] == "BC7 身份题"
        assert record["user_answer"] == "B"
        assert record["reference_answer"] == "A"
        assert record["analysis"] == "BC7 身份解析"
        assert record["question_bank_id"] is None      # chapter-only identity
        # the internal source id is never part of the public contract
        assert "question_source_id" not in record
        assert "question_source_type" not in record
        assert "question_scope_key" not in record
        assert "legacy" not in record
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id.in_(ids)).delete(synchronize_session=False)
        db_session.commit()


def test_module_filter_does_not_leak_across_subjects(client, db_session, chapter_bank):
    register_and_login(client, "bc7_modules")
    user = db_session.query(User).filter(User.username == "bc7_modules").first()
    qid = chapter_bank["BC7 章节选择一"].id
    _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})

    assert len(_items(client, f"?module={MODULE}")) == 1
    assert _items(client, "?module=data_structure") == []
    assert _items(client, "?module=computer_network") == []
    assert _items(client, "?module=operating_system&status=resolved") == []
    assert len(_items(client, "?module=operating_system&status=active")) == 1
    assert len(_states(db_session, user, module_key=MODULE)) == 1
    assert _states(db_session, user, module_key="data_structure") == []


def test_reads_are_side_effect_free_and_never_write_mastery(client, db_session, chapter_bank):
    register_and_login(client, "bc7_side_effect")
    user = db_session.query(User).filter(User.username == "bc7_side_effect").first()
    qid = chapter_bank["BC7 章节选择一"].id
    _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})

    state = _states(db_session, user)[0]
    snapshot = (state.status, state.wrong_count, state.resolved_at, state.updated_at)
    state_id = state.id

    assert len(_items(client)) == 1
    assert client.get(f"/wrong-answers/{state_id}").status_code == 200
    assert client.get(f"/wrong-answers/{state_id}").status_code == 200

    db_session.expire_all()
    state = db_session.query(WrongAnswerState).filter(WrongAnswerState.id == state_id).one()
    assert (state.status, state.wrong_count, state.resolved_at,
            state.updated_at) == snapshot
    # resolving a wrong question is not mastery — the knowledge writer is never reached
    assert db_session.query(UserKnowledgeProgress).filter(
        UserKnowledgeProgress.username == "bc7_side_effect").count() == 0
    assert state.status == "active", "WRONG_RESOLUTION_IMPLIES_MASTERY = NO"


def test_legacy_stores_are_not_product_authority(client, db_session, chapter_bank):
    """A legacy row cannot open, close or duplicate what the canonical surface reports."""
    register_and_login(client, "bc7_authority")
    user = db_session.query(User).filter(User.username == "bc7_authority").first()
    qid = chapter_bank["BC7 章节选择一"].id
    _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})

    # A legacy blank row for the SAME question must change nothing on the surface.
    db_session.add(ExamWrongQuestion(
        username="bc7_authority", subject_key=MODULE, question_bank_id=qid,
        question_type="choice", user_answer="", status="active", mastered=False,
        created_at=datetime(2024, 1, 1)))
    db_session.commit()
    wrong_legacy.run_legacy_wrong_backfill(db_session)
    db_session.expire_all()

    items = _items(client)
    assert len(items) == 1
    assert items[0]["user_answer"] == "B", "the factual answer wins over the legacy blank"
    assert len(_states(db_session, user)) == 1


def test_figure_wrong_record_reuses_the_past_paper_resource_contract(client, db_session):
    """A figure question in the wrong book emits the SAME URL contract BC6 established."""
    register_and_login(client, "bc7_figure")
    # The real 2022 computer_organization figures live on disk, not in the test database, so
    # the paper is seeded against the REAL question 12 and its REAL figure. The answer is
    # then deliberately wrong, so the test cannot pass because the answer happened to be right.
    import exam_past_paper
    assert exam_past_paper.resources_for(SUBJECT, YEAR, 12), (
        "this paper's question 12 must carry a figure for the test to mean anything")

    row = ExamQuestionBank(
        subject_key=SUBJECT, subject_name="计算机组成原理", source_type="past_paper",
        visibility="public", year=YEAR, question_number=12, question_type="choice",
        stem="BC7 图题", options_json=json.dumps({"A": "甲", "B": "乙"}),
        standard_answer="A", is_active=True, source_ref="past_paper:2022-Q12")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    try:
        created = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts",
                              json={"year": YEAR}).json()
        submitted = client.post(f"/exam/11408/{SUBJECT}/past-paper-attempts/"
                                f"{created['attempt_id']}/submit", json={"answers": {"12": "B"}})
        assert submitted.status_code == 200, submitted.text

        record = _items(client)[0]
        assert record["question_number"] == 12
        assert record["resources"], "question 12 of the real 2022 paper carries figures"
        urls = [r["url"] for r in record["resources"]]
        assert urls == [r.url for r in exam_past_paper.resources_for(SUBJECT, YEAR, 12)], (
            "the wrong book must emit the SAME resource URLs as the paper itself")
        assert all(u.startswith("/exam/11408/past-paper-images/") for u in urls)
        assert all(not u.startswith(("http://", "https://", "file:")) for u in urls)
        assert "C:" not in "".join(urls)
    finally:
        db_session.query(ExamQuestionBank).filter(
            ExamQuestionBank.id == row.id).delete(synchronize_session=False)
        db_session.commit()


def test_two_users_cannot_see_each_others_wrong_state(client, db_session, chapter_bank):
    register_and_login(client, "bc7_owner")
    qid = chapter_bank["BC7 章节选择一"].id
    _chapter_submit(client, _chapter_flow(client, [qid]), {str(qid): "B"})
    state_id = _items(client)[0]["wrong_record_id"]

    client.cookies.clear()
    register_and_login(client, "bc7_intruder")
    assert _items(client) == []
    assert client.get(f"/wrong-answers/{state_id}").status_code == 404
    assert client.patch(f"/wrong-answers/{state_id}",
                        json={"resolved": True}).status_code == 404


def test_canonical_surface_is_typed_in_openapi(client):
    """No required wrong-answer operation may declare `unknown` request or success."""
    spec = client.get("/openapi.json").json()
    list_op = spec["paths"]["/wrong-answers"]["get"]
    schema = list_op["responses"]["200"]["content"]["application/json"]["schema"]
    assert schema.get("$ref") == "#/components/schemas/WrongAnswerListResponse"

    record = spec["components"]["schemas"]["WrongAnswerRecord"]
    # Every field the record always carries is required; the source-specific ones are present
    # and nullable, which is how the frontend avoids branching on where a row came from.
    assert set(record["required"]) >= {"wrong_record_id", "status", "service_namespace",
                                       "module_key", "module_name", "source_kind",
                                       "source_label"}
    assert set(record["properties"]) >= {
        "wrong_record_id", "status", "service_namespace", "module_key", "module_name",
        "source_kind", "source_label", "question_type", "stem", "options", "user_answer",
        "reference_answer", "analysis", "year", "question_number", "question_bank_id",
        "knowledge_point_id", "resources", "first_wrong_at", "last_wrong_at", "resolved_at",
        "repeat_wrong_count"}
    assert record["properties"]["source_kind"]["enum"] == [
        "chapter_practice", "past_paper", "ai_generated", "other"]
    assert record["properties"]["status"]["enum"] == ["active", "resolved"]

    detail = spec["paths"]["/wrong-answers/{state_id}"]["get"]["responses"]["200"][
        "content"]["application/json"]["schema"]
    assert detail.get("$ref") == "#/components/schemas/WrongAnswerDetailResponse"
    patch_schema = spec["paths"]["/wrong-answers/{state_id}"]["patch"]["responses"]["200"][
        "content"]["application/json"]["schema"]
    assert patch_schema.get("$ref") == "#/components/schemas/WrongAnswerRecord"

    for name, model in spec["components"]["schemas"].items():
        if name.startswith("WrongAnswer"):
            assert "additionalProperties" not in model or model.get(
                "additionalProperties") is False


# ================================================================ E. real DB safety


def test_real_app_db_is_never_mutated_by_this_suite():
    """The suite only ever copies. This pins the fact for the BC7 report."""
    con = sqlite3.connect(f"file:{APP_DB.as_posix()}?mode=ro", uri=True)
    try:
        tables = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        canonical = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
            (CANONICAL_TABLE,)).fetchone()[0]
        blank_legacy = con.execute(
            "SELECT COUNT(*) FROM exam_wrong_questions WHERE COALESCE(user_answer,'')=''"
        ).fetchone()[0]
        pp_dupes = con.execute(
            "SELECT COUNT(*) FROM past_paper_wrong_questions").fetchone()[0]
    finally:
        con.close()
    assert integrity == "ok"
    assert tables == 72, "the deployed baseline table count is unchanged"
    assert canonical == 0, "the canonical table still arrives via migration, not by accident"
    assert blank_legacy == 0 and pp_dupes == 0, "the real wrong stores hold no rows"
