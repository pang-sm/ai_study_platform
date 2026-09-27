"""P3.1: a course the learner holds is a course — whatever it is named.

The material scope used to be decided by a fixed table of known course names, so a course that
came from a recommendation (线性代数, 概率统计, 大学物理 …) or was declared by hand was refused
with 400 by every material endpoint even though the learner plainly had it. These tests pin the
general rule: identity comes from the learner's OWN course set, the fixed table stays a catalogue
of known spellings, and scope isolation is unchanged.
"""
from __future__ import annotations

import pytest

from conftest import register_and_login
from models import StudyMaterial, User

DECLARED = ["数据结构", "线性代数", "概率统计"]
RECOMMENDED_NEW = "线性代数"
OTHER_NEW = "概率统计"


def _declare(client, courses, major="计算机科学与技术", grade="大二"):
    reply = client.post("/course-learning/onboarding", json={
        "major": major, "grade": grade, "semester": "",
        "selected_courses": courses, "recommended_courses": courses[:1],
        "material_types": [], "course_goals": {}, "onboarding_completed": True,
    })
    assert reply.status_code == 200, reply.text
    return reply.json()


def _add_material(db_session, username, course):
    db_session.add(StudyMaterial(
        username=username, subject=course, course_id=course, subject_key=course,
        file_type="pdf", original_filename=f"{course}讲义.pdf", file_path=f"materials/{course}.pdf",
        file_size=10, extracted_text="内容", summary="讲义", parse_status="success", chunk_count=2))
    db_session.commit()
    db_session.rollback()


def _materials(client, course_id, **more):
    return client.get("/materials", params={"course_id": course_id, **more})


# ── A: a recommended course forms a canonical course scope ────

def test_a_recommended_course_forms_a_canonical_scope(client, db_session):
    register_and_login(client, "p31-scope")
    _declare(client, DECLARED)

    from main import owned_course_scope_forms, resolve_material_scope

    user = db_session.query(User).filter_by(username="p31-scope").one()
    scope = resolve_material_scope(RECOMMENDED_NEW, RECOMMENDED_NEW, RECOMMENDED_NEW,
                                   "course_learning",
                                   owned_forms=owned_course_scope_forms(db_session, user))

    # The course is its own identity and its own subject, exactly like a mapped course.
    assert scope["course_id"] == RECOMMENDED_NEW
    assert scope["subject_key"] == RECOMMENDED_NEW
    assert scope["subject"] == RECOMMENDED_NEW
    assert scope["track"] == "course_learning"


def test_a_course_nobody_holds_is_still_refused(client, db_session):
    register_and_login(client, "p31-scope-refused")
    _declare(client, DECLARED)

    from main import owned_course_scope_forms, resolve_material_scope

    user = db_session.query(User).filter_by(username="p31-scope-refused").one()
    forms = owned_course_scope_forms(db_session, user)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as refusal:
        resolve_material_scope("量子力学导论", "", "", "course_learning", owned_forms=forms)
    assert refusal.value.status_code == 400
    # And with no ownership context at all, the catalogue is still the only thing accepted.
    with pytest.raises(HTTPException):
        resolve_material_scope(RECOMMENDED_NEW, "", "", "course_learning")
    # Every declared course is in the set, in every spelling the product writes.
    assert RECOMMENDED_NEW in forms and "数据结构" in forms and "data_structure" in forms


# ── B/C: materials — empty is a state, not an error ───────────

def test_a_held_course_with_no_materials_lists_empty(client, db_session):
    register_and_login(client, "p31-empty")
    _declare(client, DECLARED)

    reply = _materials(client, RECOMMENDED_NEW)

    assert reply.status_code == 200, reply.text
    assert reply.json()["materials"] == []


def test_a_held_course_lists_its_own_materials(client, db_session):
    register_and_login(client, "p31-rows")
    _declare(client, DECLARED)
    _add_material(db_session, "p31-rows", RECOMMENDED_NEW)
    _add_material(db_session, "p31-rows", OTHER_NEW)

    reply = _materials(client, RECOMMENDED_NEW)

    assert reply.status_code == 200, reply.text
    rows = reply.json()["materials"]
    assert [row["course_id"] for row in rows] == [RECOMMENDED_NEW]
    assert rows[0]["file_name"].startswith(RECOMMENDED_NEW)


def test_uploading_into_a_held_course_is_accepted(client, db_session):
    """The workspace upload re-resolves the course's scope, so it failed for the same reason."""
    register_and_login(client, "p31-upload")
    _declare(client, DECLARED)

    reply = client.post(
        f"/course-learning/courses/{RECOMMENDED_NEW}/materials",
        files={"file": ("线性代数笔记.txt", b"vector spaces", "text/plain")})

    assert reply.status_code == 200, reply.text
    listed = _materials(client, RECOMMENDED_NEW)
    assert [row["course_id"] for row in listed.json()["materials"]] == [RECOMMENDED_NEW]


# ── D: an illegal scope is still refused ─────────────────────

def test_another_learners_course_is_not_a_scope_for_this_one(client, db_session):
    register_and_login(client, "p31-owner")
    _declare(client, ["量子力学导论"])
    _add_material(db_session, "p31-owner", "量子力学导论")
    client.post("/logout")

    register_and_login(client, "p31-intruder")
    _declare(client, DECLARED)

    # The name is legitimate — for the other learner. Not for this one.
    assert _materials(client, "量子力学导论").status_code == 400
    # And nothing of theirs can be listed under a course this caller does hold.
    assert _materials(client, RECOMMENDED_NEW).json()["materials"] == []


def test_the_request_shape_is_still_validated(client, db_session):
    register_and_login(client, "p31-shape")
    _declare(client, DECLARED)
    _add_material(db_session, "p31-shape", RECOMMENDED_NEW)

    # A course id is required for a scoped list, and a display name is not a scope on its own.
    assert _materials(client, "", subject_key=RECOMMENDED_NEW).status_code == 400
    assert client.get("/materials", params={"subject": RECOMMENDED_NEW}).status_code == 400
    # A name that contradicts the course id is refused rather than guessed.
    assert _materials(client, RECOMMENDED_NEW, subject_key=OTHER_NEW).status_code == 400
    assert _materials(client, RECOMMENDED_NEW, subject=OTHER_NEW).status_code == 400
    # No scope at all is the caller's whole library (plus the shared system rows the product
    # makes visible to everyone) — never another learner's material.
    unscoped = client.get("/materials")
    assert unscoped.status_code == 200
    names = [row["file_name"] for row in unscoped.json()["materials"]]
    assert f"{RECOMMENDED_NEW}讲义.pdf" in names
    assert all("量子力学导论" not in name for name in names)


# ── E/F: chat scope and capability are unchanged ──────────────

def test_two_recommended_courses_keep_separate_conversations(client, db_session, monkeypatch):
    from ai.providers import FakeProvider
    from models import ChatSession
    from usage import service as usage_service
    from usage.models import AIRequest

    register_and_login(client, "p31-chat")
    _declare(client, DECLARED)
    user = db_session.query(User).filter_by(username="p31-chat").one()
    usage_service.activate_subscription(db_session, user.id, "advanced", 30)
    user_id = user.id
    db_session.rollback()
    monkeypatch.setattr("ai.orchestrator.default_provider_factory",
                        lambda name: FakeProvider(provider=name, input_tokens=20, output_tokens=20))

    def ask(course, message):
        return client.post("/chat", json={
            "message": message, "service_key": "course_learning", "course_id": course,
            "subject_key": "", "subject": "", "grade": "", "major": "", "material_ids": [],
            "branch_id": "", "hidden_instruction": "", "mastery_level": "", "learning_goal": "",
            "model_preference": "", "session_id": None, "model_id": None,
            "thinking_mode": "standard"})

    assert ask(RECOMMENDED_NEW, "特征值是什么").status_code == 200
    assert ask(OTHER_NEW, "条件概率是什么").status_code == 200

    db_session.expire_all()
    sessions = (db_session.query(ChatSession)
                .filter(ChatSession.user_id == user_id).order_by(ChatSession.id).all())
    assert [session.subject for session in sessions] == [RECOMMENDED_NEW, OTHER_NEW]

    linear = client.get(f"/chat/history?course={RECOMMENDED_NEW}").json()["sessions"]
    probability = client.get(f"/chat/history?course={OTHER_NEW}").json()["sessions"]
    assert [session["title"] for session in linear] == ["特征值是什么"]
    assert [session["title"] for session in probability] == ["条件概率是什么"]

    # A course with no materials still answers through plain tutoring.
    requests = db_session.query(AIRequest).filter(AIRequest.user_id == user_id).all()
    assert {request.capability for request in requests} == {"tutor.chat"}


# ── G: the mapped courses do not regress ─────────────────────

def test_mapped_courses_resolve_exactly_as_before(client, db_session):
    register_and_login(client, "p31-legacy")
    _declare(client, DECLARED)
    _add_material(db_session, "p31-legacy", "数据结构")

    from main import owned_course_scope_forms, resolve_material_scope

    user = db_session.query(User).filter_by(username="p31-legacy").one()
    forms = owned_course_scope_forms(db_session, user)

    # Both spellings of a catalogued course keep their existing scope.
    by_name = resolve_material_scope("数据结构", "数据结构", "数据结构", "course_learning",
                                     owned_forms=forms)
    by_key = resolve_material_scope("data_structure", "data_structure", "数据结构",
                                    "course_learning", owned_forms=forms)
    assert (by_name["course_id"], by_name["subject_key"]) == ("数据结构", "数据结构")
    assert (by_key["course_id"], by_key["subject_key"]) == ("data_structure", "data_structure")
    # The exam and programming scopes are untouched.
    exam = resolve_material_scope("data_structure_11408", "data_structure", "", "",
                                  owned_forms=forms)
    assert exam["track"] == "exam_11408"
    programming = resolve_material_scope("python_programming", "programming", "", "programming",
                                         owned_forms=forms)
    assert programming["track"] == "programming"

    # And the existing list behaviour for a catalogued course is unchanged.
    listed = _materials(client, "数据结构")
    assert listed.status_code == 200
    assert [row["course_id"] for row in listed.json()["materials"]] == ["数据结构"]


def test_a_new_course_material_counts_toward_the_course_quota(client, db_session):
    """A held course's uploads are course_learning files, not an unmapped 'legacy' bucket."""
    from main import _material_domain

    assert _material_domain(RECOMMENDED_NEW, RECOMMENDED_NEW) == "course_learning"
    assert _material_domain("数据结构", "数据结构") == "course_learning"
    assert _material_domain("data_structure", "data_structure") == "course_learning"
    assert _material_domain("data_structure_11408", "data_structure") == "exam_11408"
    assert _material_domain("python_programming", "programming") == "programming"
    assert _material_domain("", "") == "legacy"
