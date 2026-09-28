"""SECURITY_S1B — ownership and visibility for the CS408 question bank.

The pre-fix chain: learner A could write a ``visibility=public, source_type=chapter`` row that
every learner then saw and was graded against, and A's ``private`` rows were reachable by id
through ``chapter-practice`` — B named the id, it was captured into B's attempt, and submit
returned A's ``standard_answer`` and ``analysis``.

These tests pin the three rules that close it:

* a learner cannot author shared content at all (the bank is official, server-owned content);
* a row is visible only when it is public or the caller owns it;
* the client's ``question_ids`` are a request, never an authorization — every id is re-checked
  and one bad id refuses the whole attempt.
"""
import json

import pytest
from fastapi.testclient import TestClient

import database
import main
import models
from conftest import register_and_login
from exam_question_bank_access import (
    UNAVAILABLE_CODE,
    is_usable_in_chapter_practice,
    is_visible_to,
    visible_query,
)

MODULE = "data_structure"
OTHER_MODULE = "operating_system"
PRIVATE_STEM = "S1B 私有题干"
PUBLIC_STEM = "S1B 官方题干"
PRIVATE_ANSWER = "S1B-private-answer"
PRIVATE_ANALYSIS = "S1B-private-analysis"

_created_ids: list[int] = []


def _mk(db, *, subject=MODULE, visibility="public", owner=None, source_type="chapter",
        stem=PUBLIC_STEM, answer="A", analysis="官方解析", active=True, kp="1.1"):
    row = models.ExamQuestionBank(
        subject_key=subject, subject_name=subject, source_type=source_type,
        visibility=visibility, owner_username=owner, knowledge_point_id=kp,
        knowledge_point_name="知识点", knowledge_point_path="",
        question_type="choice", stem=stem, options_json=json.dumps({"A": "甲", "B": "乙"}),
        standard_answer=answer, analysis=analysis, is_active=active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _created_ids.append(row.id)
    return row


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    db = database.SessionLocal()
    try:
        if _created_ids:
            db.query(models.ExamWrongQuestion).filter(
                models.ExamWrongQuestion.question_bank_id.in_(_created_ids)
            ).delete(synchronize_session=False)
            db.query(models.ExamQuestionDoneRecord).filter(
                models.ExamQuestionDoneRecord.question_bank_id.in_(_created_ids)
            ).delete(synchronize_session=False)
            db.query(models.ExamQuestionBank).filter(
                models.ExamQuestionBank.id.in_(_created_ids)
            ).delete(synchronize_session=False)
            db.commit()
        _created_ids.clear()
    finally:
        db.close()


def _make_admin(client, role="operator"):
    register_and_login(client, f"s1b-admin-{role}")
    db = database.SessionLocal()
    try:
        user = db.query(models.User).filter_by(username=f"s1b-admin-{role}").one()
        user.is_admin = 1
        user.admin_role = role
        db.commit()
    finally:
        db.close()
    return f"s1b-admin-{role}"


# ── §14: the predicate itself ──────────────────────────────────────────────────────

def test_visibility_predicate(db_session):
    owner_row = _mk(db_session, visibility="private", owner="s1b-owner")
    public_row = _mk(db_session, visibility="public", owner=None)
    inactive_public = _mk(db_session, visibility="public", active=False, kp="1.2")
    other_subject = _mk(db_session, subject=OTHER_MODULE, visibility="public", kp="1.3")
    other_source = _mk(db_session, source_type="past_paper", visibility="public", kp="1.4")

    assert is_visible_to(public_row, "anyone") is True
    assert is_visible_to(owner_row, "s1b-owner") is True
    assert is_visible_to(owner_row, "someone-else") is False
    assert is_visible_to(owner_row, None) is False

    usable = dict(subject_key=MODULE, username="s1b-owner")
    assert is_usable_in_chapter_practice(public_row, **usable) is True
    assert is_usable_in_chapter_practice(owner_row, **usable) is True
    assert is_usable_in_chapter_practice(owner_row, subject_key=MODULE, username="other") is False
    assert is_usable_in_chapter_practice(inactive_public, **usable) is False
    assert is_usable_in_chapter_practice(other_subject, **usable) is False
    assert is_usable_in_chapter_practice(other_source, **usable) is False

    # The query form and the row form must agree — a route using one and a guard using the
    # other cannot drift apart.
    ids = {r.id for r in visible_query(db_session.query(models.ExamQuestionBank), "s1b-owner").all()}
    assert owner_row.id in ids and public_row.id in ids
    assert other_subject.id in ids  # visible, just not usable in *this* subject's chapter flow


def test_query_form_hides_foreign_private_rows(db_session):
    foreign_private = _mk(db_session, visibility="private", owner="s1b-foreign")
    mine = _mk(db_session, visibility="private", owner="s1b-me", kp="1.2")

    ids = {r.id for r in visible_query(db_session.query(models.ExamQuestionBank), "s1b-me").all()}
    assert mine.id in ids
    assert foreign_private.id not in ids

    anon = {r.id for r in visible_query(db_session.query(models.ExamQuestionBank), None).all()}
    assert mine.id not in anon and foreign_private.id not in anon


# ── the historical cross-user exploit ──────────────────────────────────────────────

def test_owner_reads_own_private_question(client, db_session):
    register_and_login(client, "s1b-owner-a")
    row = _mk(db_session, visibility="private", owner="s1b-owner-a", stem=PRIVATE_STEM)

    listed = client.get(f"/exam/11408/{MODULE}/question-bank/questions").json()
    assert row.id in {i["id"] for i in listed["items"]}


def test_other_learner_cannot_list_a_private_question(client, db_session):
    row = _mk(db_session, visibility="private", owner="s1b-owner-b", stem=PRIVATE_STEM)

    other = TestClient(client.app)
    try:
        register_and_login(other, "s1b-other-b")
        listed = other.get(f"/exam/11408/{MODULE}/question-bank/questions").json()
        assert row.id not in {i["id"] for i in listed["items"]}
        listed = other.get("/exam/11408/data_structure/chapter-practice/questions").json()
        assert PRIVATE_STEM not in json.dumps(listed, ensure_ascii=False)
    finally:
        other.close()


def test_attempt_creation_refuses_a_foreign_private_question(client, db_session):
    """The exact id is known and still refused — and no attempt is created."""
    row = _mk(db_session, visibility="private", owner="s1b-owner-c", stem=PRIVATE_STEM)

    other = TestClient(client.app)
    try:
        register_and_login(other, "s1b-other-c")
        before = db_session.query(models.ExamPracticeAttempt).filter_by(username="s1b-other-c").count()

        response = other.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                              json={"question_ids": [row.id]})

        assert response.status_code == 400, response.text
        assert response.json()["detail"]["code"] == UNAVAILABLE_CODE
        db_session.expire_all()
        after = db_session.query(models.ExamPracticeAttempt).filter_by(username="s1b-other-c").count()
        assert after == before, "a refused selection must not create an attempt"
    finally:
        other.close()


def test_submit_cannot_disclose_a_foreign_private_answer(client, db_session):
    """Defence in depth for an attempt captured before this rule existed.

    The attempt row is written directly, standing in for a pre-fix capture, and submit still
    must not emit the foreign row's answer or analysis.
    """
    row = _mk(db_session, visibility="private", owner="s1b-owner-d", stem=PRIVATE_STEM,
              answer=PRIVATE_ANSWER, analysis=PRIVATE_ANALYSIS)

    other = TestClient(client.app)
    try:
        register_and_login(other, "s1b-other-d")
        legacy = models.ExamPracticeAttempt(
            username="s1b-other-d", subject_key=MODULE, practice_type="chapter",
            source_type="chapter", status="in_progress",
            question_ids_json=json.dumps([row.id]), total_questions=1,
        )
        db_session.add(legacy)
        db_session.commit()
        db_session.refresh(legacy)

        submitted = other.post(
            f"/exam/11408/{MODULE}/chapter-practice/attempts/{legacy.id}/submit",
            json={"answers": {str(row.id): "A"}},
        )
        assert submitted.status_code == 200, submitted.text
        body = json.dumps(submitted.json(), ensure_ascii=False)
        assert PRIVATE_ANSWER not in body
        assert PRIVATE_ANALYSIS not in body
        assert PRIVATE_STEM not in body

        detail = other.get(f"/exam/11408/{MODULE}/chapter-practice/attempts/{legacy.id}").json()
        detail_body = json.dumps(detail, ensure_ascii=False)
        assert PRIVATE_ANSWER not in detail_body
        assert PRIVATE_ANALYSIS not in detail_body
        assert PRIVATE_STEM not in detail_body

        db_session.delete(legacy)
        db_session.commit()
    finally:
        other.close()


def test_wrong_subject_route_cannot_consume_this_module(client, db_session):
    row = _mk(db_session, visibility="public", stem=PUBLIC_STEM)
    register_and_login(client, "s1b-subject")

    response = client.post(f"/exam/11408/{OTHER_MODULE}/chapter-practice/attempts",
                           json={"question_ids": [row.id]})
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == UNAVAILABLE_CODE


def test_wrong_subject_attempt_read_is_not_found(client, db_session):
    row = _mk(db_session, visibility="public")
    register_and_login(client, "s1b-subject-read")
    created = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                          json={"question_ids": [row.id]})
    attempt_id = created.json()["attempt_id"]

    assert client.get(
        f"/exam/11408/{OTHER_MODULE}/chapter-practice/attempts/{attempt_id}"
    ).status_code == 404


def test_inactive_question_cannot_enter_a_new_attempt(client, db_session):
    row = _mk(db_session, visibility="public", active=False)
    register_and_login(client, "s1b-inactive")

    response = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                           json={"question_ids": [row.id]})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == UNAVAILABLE_CODE


def test_past_paper_row_cannot_enter_chapter_practice(client, db_session):
    paper = _mk(db_session, source_type="past_paper", kp="")
    register_and_login(client, "s1b-paper")

    response = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                           json={"question_ids": [paper.id]})
    assert response.status_code == 400


# ── shared content integrity ───────────────────────────────────────────────────────

def test_learner_cannot_inject_public_shared_content(client, db_session):
    register_and_login(client, "s1b-inject")
    before = db_session.query(models.ExamQuestionBank).count()

    response = client.post(f"/exam/11408/{MODULE}/question-bank/questions", json={
        "stem": "S1B 伪造共享题", "source_type": "chapter", "visibility": "public",
        "standard_answer": "A", "analysis": "伪造解析",
    })

    assert response.status_code == 403, response.text
    db_session.expire_all()
    assert db_session.query(models.ExamQuestionBank).count() == before, "a refusal must write nothing"


def test_learner_cannot_author_private_content_either(client, db_session):
    """Closing only the public path would leave an unowned authoring surface behind."""
    register_and_login(client, "s1b-inject-private")
    response = client.post(f"/exam/11408/{MODULE}/question-bank/questions", json={
        "stem": "S1B 私有题", "source_type": "chapter", "visibility": "private",
    })
    assert response.status_code == 403, response.text


def test_auditor_cannot_author_shared_content(client, db_session):
    """RBAC still holds: read-only roles must not write shared content."""
    _make_admin(client, "auditor")
    response = client.post(f"/exam/11408/{MODULE}/question-bank/questions", json={
        "stem": "S1B 审计员题", "visibility": "public",
    })
    assert response.status_code == 403, response.text


def test_admin_can_author_official_content(client, db_session):
    _make_admin(client, "operator")
    response = client.post(f"/exam/11408/{MODULE}/question-bank/questions", json={
        "stem": "S1B 官方新增题", "source_type": "chapter", "visibility": "public",
        "standard_answer": "A", "analysis": "官方解析",
    })
    assert response.status_code == 200, response.text
    created_id = response.json()["id"]
    _created_ids.append(created_id)

    row = db_session.query(models.ExamQuestionBank).filter_by(id=created_id).one()
    assert row.visibility == "public"
    assert row.owner_username == "s1b-admin-operator"

    # …and learners see it, which is the point of official authoring.
    learner = TestClient(client.app)
    try:
        register_and_login(learner, "s1b-sees-official")
        listed = learner.get(f"/exam/11408/{MODULE}/chapter-practice/questions").json()
        assert "S1B 官方新增题" in json.dumps(listed, ensure_ascii=False)
    finally:
        learner.close()


# ── the normal product still works ─────────────────────────────────────────────────

def test_official_question_flows_end_to_end(client, db_session):
    row = _mk(db_session, visibility="public", stem=PUBLIC_STEM, answer="A")
    register_and_login(client, "s1b-happy")

    listed = client.get(f"/exam/11408/{MODULE}/chapter-practice/questions").json()
    assert PUBLIC_STEM in json.dumps(listed, ensure_ascii=False)
    # Pre-submit contract: the solution is not on the wire.
    for item in listed["items"]:
        assert "standard_answer" not in item and "analysis" not in item

    created = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts",
                          json={"question_ids": [row.id]})
    assert created.status_code == 200, created.text
    assert created.json()["total_questions"] == 1
    attempt_id = created.json()["attempt_id"]

    client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/answers",
                json={"answers": {str(row.id): "A"}})
    submitted = client.post(f"/exam/11408/{MODULE}/chapter-practice/attempts/{attempt_id}/submit",
                            json={"answers": {str(row.id): "A"}})
    assert submitted.status_code == 200, submitted.text

    result = next(r for r in submitted.json()["results"] if r["question_id"] == row.id)
    assert result["correct"] is True
    assert result["standard_answer"] == "A"
    assert PUBLIC_STEM in json.dumps(result, ensure_ascii=False)


def test_answer_fields_are_absent_from_every_learner_facing_list(client, db_session):
    _mk(db_session, visibility="public", stem=PUBLIC_STEM)
    _mk(db_session, visibility="private", owner="s1b-owner-e", stem=PRIVATE_STEM, kp="1.2")

    other = TestClient(client.app)
    try:
        register_and_login(other, "s1b-no-leak")
        for path in (f"/exam/11408/{MODULE}/chapter-practice/questions",
                     f"/exam/11408/{MODULE}/question-bank/stats",
                     f"/exam/11408/{MODULE}/chapter-practice/outline"):
            body = other.get(path).json()
            assert PRIVATE_STEM not in json.dumps(body, ensure_ascii=False), path
    finally:
        other.close()
