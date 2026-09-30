"""学习's data wire: one knowledge point, the explanation stored for it, and its grounding.

Three claims carry this file, and each one is asserted against stored rows or against the
request the provider actually received — never against a response body that could say
anything:

  * the point a learner studies is the ACTIVE version's, so a draft's point is unreadable
  * a stored explanation is read for free, and only an explicit regenerate buys a new one
  * which of the learner's files grounded the answer is decided by the structure's own
    recorded source, and a file that grounded nothing is never cited
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from ai.providers import FakeProvider
from conftest import register_and_login
from learning.spaces.course_learning import knowledge_structure as ks
from learning.spaces.course_learning import study_content as sc
from models import (CourseLearningPreference, KnowledgePoint, KnowledgePointStudyContent,
                    MaterialChunk, StudyMaterial, User, UserKnowledgeProgress)
from usage import service as usage_service

COURSE = "数据结构"


class RecordingProvider(FakeProvider):
    def __init__(self, calls: list, **kwargs):
        super().__init__(**kwargs)
        self.calls = calls

    def complete(self, spec):
        self.calls.append(spec)
        return dataclasses.replace(super().complete(spec),
                                   content="顺序表用一段连续的空间存放元素，插入删除要移动元素。")


@pytest.fixture
def provider(monkeypatch):
    """The provider the orchestrator reaches, with every request recorded."""
    calls: list = []
    factory = lambda *a, **k: RecordingProvider(calls, **k)  # noqa: E731
    monkeypatch.setattr("ai.orchestrator.default_provider_factory", factory)
    return calls


# ------------------------------------------------------------------ fixtures

def user_for(db, username) -> User:
    """The row the client's own request created — never a second user with the same name."""
    db.rollback()
    return db.query(User).filter_by(username=username).one()


def attach_course(db, username, course_id=COURSE):
    db.add(CourseLearningPreference(username=username, course_id=course_id,
                                    display_name=course_id, mastery_level="",
                                    learning_goal=""))
    db.commit()


def make_user(db, username) -> User:
    """A learner that never goes through HTTP — for the service-level tests only."""
    user = User(username=username, hashed_password="x", grade="freshman", major="cs")
    db.add(user)
    db.commit()
    return user


def make_material(db, username, filename, text="顺序表是连续存储", course_id=COURSE):
    material = StudyMaterial(
        username=username, course_id=course_id, subject_key=course_id,
        subject=course_id, scope_type="course", file_type="pdf",
        original_filename=filename, file_size=10, file_path=f"/tmp/{filename}",
        extracted_text=text, summary=text, allow_private_rag=True)
    db.add(material)
    db.flush()
    for index in range(2):
        db.add(MaterialChunk(
            material_id=material.id, username=username, course_id=course_id,
            subject_key=course_id, subject=course_id, chunk_index=index,
            chunk_text=f"{text} 片段 {index}", chunk_summary=f"{text} 片段 {index}",
            source_filename=filename))
    db.commit()
    return material


def published_structure(db, username, source_mode="ai_generated", material_ids=None,
                        point_title="顺序表") -> int:
    """An ACTIVE structure with one chapter and one point — no provider involved."""
    user = user_for(db, username)
    chapters = [{"title": "第2章 线性表",
                 "points": [{"title": point_title, "description": "顺序存储的线性表",
                             "source_hint": "", "origin": ks.ORIGIN_AI_INFERRED}]}]
    created = ks.create_draft(db, user, COURSE, source_mode=source_mode, chapters=chapters,
                              source_file_ids=material_ids or [], title="结构", goal="")
    ks.confirm(db, user, COURSE, created.id)
    active = ks.active_structure(db, username, COURSE)
    point = (db.query(KnowledgePoint)
             .filter(KnowledgePoint.structure_id == active.id,
                     KnowledgePoint.parent_id.isnot(None)).first())
    return point.id


def draft_structure(db, username, point_title="草稿点") -> int:
    user = user_for(db, username)
    created = ks.create_draft(db, user, COURSE, source_mode="ai_generated",
                              chapters=[{"title": "草稿章",
                                         "points": [{"title": point_title, "description": "",
                                                     "source_hint": "",
                                                     "origin": ks.ORIGIN_AI_INFERRED}]}],
                              source_file_ids=[], title="草稿", goal="")
    point = (db.query(KnowledgePoint)
             .filter(KnowledgePoint.structure_id == created.id,
                     KnowledgePoint.parent_id.isnot(None)).first())
    return point.id


def activate(db, username) -> int:
    """A paid tier, granted the way the product grants one — the AI gate reads THIS."""
    user = user_for(db, username)
    usage_service.activate_subscription(db, user.id, "advanced", 30)
    user_id = user.id
    db.rollback()
    return user_id


def paid_learner(client, db, username) -> str:
    register_and_login(client, username)
    attach_course(db, username)
    activate(db, username)
    return username


def study_content_url(point_id, course=COURSE) -> str:
    return f"/course-learning/courses/{course}/knowledge-points/{point_id}/study-content"


# ══════════════════════════════════════════════════ identity


def test_a_point_of_the_active_version_is_readable(client, db_session, provider):
    username = paid_learner(client, db_session, "study-active")
    point_id = published_structure(db_session, username)

    reply = client.post(study_content_url(point_id))
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["knowledge_point_id"] == point_id
    assert body["content"]
    assert body["cached"] is False


def test_a_point_of_a_draft_is_not_readable(client, db_session, provider):
    """A draft is the question "do I want this?", not the course the learner is studying."""
    username = paid_learner(client, db_session, "study-draft")
    published_structure(db_session, username)
    point_id = draft_structure(db_session, username)

    reply = client.post(study_content_url(point_id))
    assert reply.status_code == 404, reply.text


def test_another_learners_point_is_not_readable(client, db_session, provider):
    owner = make_user(db_session, "study-owner")
    attach_course(db_session, owner.username)
    point_id = published_structure(db_session, owner.username)

    username = paid_learner(client, db_session, "study-other")
    assert username != owner.username

    reply = client.post(study_content_url(point_id))
    assert reply.status_code == 404, reply.text


# ══════════════════════════════════════════════════ the cache


def test_a_stored_explanation_is_read_without_calling_the_model(client, db_session, provider):
    username = paid_learner(client, db_session, "study-cache")
    point_id = published_structure(db_session, username)

    first = client.post(study_content_url(point_id))
    assert first.status_code == 200
    calls_after_first = len(provider)
    assert calls_after_first >= 1

    read = client.get(study_content_url(point_id))
    assert read.status_code == 200, read.text
    assert read.json()["content"] == first.json()["content"]
    assert read.json()["cached"] is True
    # The model was NOT called again: a reload is free.
    assert len(provider) == calls_after_first

    again = client.post(study_content_url(point_id))
    assert again.status_code == 200
    assert again.json()["cached"] is True
    assert len(provider) == calls_after_first


def test_nothing_stored_answers_null_rather_than_an_empty_explanation(client, db_session, provider):
    username = paid_learner(client, db_session, "study-empty")
    point_id = published_structure(db_session, username)

    read = client.get(study_content_url(point_id))
    assert read.status_code == 200, read.text
    assert read.json() is None
    assert provider == []


def test_regenerate_buys_a_new_explanation(client, db_session, provider):
    username = paid_learner(client, db_session, "study-regen")
    point_id = published_structure(db_session, username)

    client.post(study_content_url(point_id))
    before = len(provider)
    reply = client.post(study_content_url(point_id), params={"regenerate": "true"})
    assert reply.status_code == 200, reply.text
    assert len(provider) == before + 1


def test_exactly_one_row_is_kept_per_point(client, db_session, provider):
    username = paid_learner(client, db_session, "study-one-row")
    point_id = published_structure(db_session, username)

    for regenerate in ("false", "true", "true"):
        client.post(study_content_url(point_id), params={"regenerate": regenerate})

    db_session.rollback()
    rows = (db_session.query(KnowledgePointStudyContent)
            .filter(KnowledgePointStudyContent.username == username,
                    KnowledgePointStudyContent.knowledge_point_id == point_id).all())
    assert len(rows) == 1


# ══════════════════════════════════════════════════ grounding


def test_a_selected_material_structure_grounds_in_its_own_files(db_session):
    user = make_user(db_session, "study-selected")
    attach_course(db_session, user.username)
    material = make_material(db_session, user.username, "讲义.pdf")
    other = make_material(db_session, user.username, "别的书.pdf")
    point_id = published_structure(db_session, user.username,
                                   source_mode="selected_materials",
                                   material_ids=[material.id])

    mode, ids = sc.grounding_plan(db_session, user.username, COURSE, point_id)
    assert mode == sc.GROUNDING_SELECTED_MATERIALS
    assert material.id in ids
    # A file the structure did not record is not a candidate: its own record decides.
    assert other.id not in ids


def test_an_ai_structure_grounds_in_the_course_library_the_learner_later_uploaded(db_session):
    """The point of the rule: a structure generated first, a textbook uploaded afterwards."""
    user = make_user(db_session, "study-ai-later")
    attach_course(db_session, user.username)
    point_id = published_structure(db_session, user.username, source_mode="ai_generated")
    mode, ids = sc.grounding_plan(db_session, user.username, COURSE, point_id)
    assert mode == sc.GROUNDING_AI_GENERATED
    assert ids == []

    make_material(db_session, user.username, "教材.pdf", text="顺序表的插入与删除")
    chunks = sc._retrieve(db_session, user.username, COURSE, "顺序表 插入 删除",
                          sc.GROUNDING_AI_GENERATED, [])
    assert chunks, "the course library is what the ai_generated branch searches"
    assert any(chunk["source_filename"] == "教材.pdf" for chunk in chunks)


def test_a_structure_with_no_material_at_all_grounds_in_nothing(db_session):
    user = make_user(db_session, "study-bare")
    attach_course(db_session, user.username)
    published_structure(db_session, user.username, source_mode="ai_generated")

    chunks = sc._retrieve(db_session, user.username, COURSE, "顺序表",
                          sc.GROUNDING_AI_GENERATED, [])
    assert chunks == []
    text, citations = sc._render_grounding(chunks)
    assert text == "" and citations == []


def test_a_citation_names_a_file_that_actually_grounded_the_answer(db_session):
    user = make_user(db_session, "study-cite")
    attach_course(db_session, user.username)
    make_material(db_session, user.username, "讲义.pdf", text="顺序表的存储结构")

    chunks = sc._retrieve(db_session, user.username, COURSE, "顺序表 存储结构",
                          sc.GROUNDING_AI_GENERATED, [])
    text, citations = sc._render_grounding(chunks)
    assert text
    assert [citation["filename"] for citation in citations] == ["讲义.pdf"]
    assert citations[0]["snippet"]


def test_an_ungrounded_explanation_carries_no_citation(client, db_session, provider):
    """No file was read, so none is named — a citation block would be a fabrication."""
    username = paid_learner(client, db_session, "study-nocite")
    point_id = published_structure(db_session, username)

    body = client.post(study_content_url(point_id)).json()
    assert body["citations"] == []
    assert body["grounding_mode"] == sc.GROUNDING_NONE
    # The explanation still exists: no material is a legal state, not a dead end.
    assert body["content"]


def test_a_material_grounded_explanation_names_the_file(client, db_session, provider):
    username = paid_learner(client, db_session, "study-cite-http")
    make_material(db_session, username, "讲义.pdf", text="顺序表的存储结构")
    point_id = published_structure(db_session, username, source_mode="ai_generated",
                                   point_title="顺序表 存储结构")

    body = client.post(study_content_url(point_id)).json()
    assert body["citations"], body
    assert body["citations"][0]["filename"] == "讲义.pdf"


def test_the_prompt_carries_the_learner_material_and_the_point(client, db_session, provider):
    """The model is told which point it is explaining and which file to stay close to."""
    username = paid_learner(client, db_session, "study-prompt")
    make_material(db_session, username, "讲义.pdf", text="顺序表的存储结构")
    point_id = published_structure(db_session, username, point_title="顺序表 存储结构")

    assert client.post(study_content_url(point_id)).status_code == 200

    spec = provider[-1]
    request = "\n".join(message.content for message in spec.messages[:-1])
    # The last message is the learner's own turn; the setting is stated in the system prompt.
    last = spec.messages[-1].content
    assert "顺序表 存储结构" in request + last
    assert "讲义.pdf" in last, "the material block belongs to the turn being answered"
    # The call carries the point as its own identity too — the accounting row records which
    # course and which point produced the answer, not just that some AI call happened.
    from usage.models import AIRequest

    user = user_for(db_session, username)
    row = (db_session.query(AIRequest).filter(AIRequest.user_id == user.id)
           .order_by(AIRequest.id.desc()).first())
    assert row is not None
    assert row.service_namespace == "course_learning"
    snapshot = row.context_json or {}
    assert snapshot.get("course_id") == COURSE
    assert snapshot.get("knowledge_point_id") == str(point_id)


# ══════════════════════════════════════════════════ decoupling


def test_reading_an_explanation_moves_no_learning_state(client, db_session, provider):
    """Opening the page is not studying, and an explanation is not a verdict."""
    username = paid_learner(client, db_session, "study-decoupled")
    point_id = published_structure(db_session, username)

    assert client.post(study_content_url(point_id)).status_code == 200

    db_session.rollback()
    progress = (db_session.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.username == username,
                        UserKnowledgeProgress.knowledge_point_id == point_id).first())
    assert progress is None, "generating an explanation is not a learning fact"


def test_the_four_states_persist_through_the_knowledge_progress_route(client, db_session):
    """The four-state control writes the row the whole product already reads."""
    username = paid_learner(client, db_session, "study-states")
    point_id = published_structure(db_session, username)

    for status in ("learning", "mastered", "review_due", "not_started"):
        reply = client.put(f"/knowledge-points/{point_id}/progress",
                           json={"username": username, "status": status})
        assert reply.status_code == 200, reply.text
        db_session.rollback()
        row = (db_session.query(UserKnowledgeProgress)
               .filter(UserKnowledgeProgress.username == username,
                       UserKnowledgeProgress.knowledge_point_id == point_id).first())
        assert row is not None and row.status == status, status


def test_the_active_structures_points_are_the_ones_the_page_serves(client, db_session):
    """The nav's read is the ACTIVE version — a draft's points must not appear in it."""
    username = paid_learner(client, db_session, "study-nav")
    published_structure(db_session, username)

    listed = client.get("/knowledge-points", params={"course_id": COURSE}).json()
    assert "顺序表" in {point["title"] for point in listed["knowledge_points"]}

    draft_structure(db_session, username, point_title="草稿点")

    listed = client.get("/knowledge-points", params={"course_id": COURSE}).json()
    titles = {point["title"] for point in listed["knowledge_points"]}
    assert "顺序表" in titles
    assert "草稿点" not in titles


def test_a_course_with_no_structure_serves_no_points(client, db_session):
    username = "study-none"
    register_and_login(client, username)
    attach_course(db_session, username)

    listed = client.get("/knowledge-points", params={"course_id": COURSE}).json()
    assert listed["knowledge_points"] == []

    structure = client.get(f"/course-learning/courses/{COURSE}/knowledge-structure").json()
    assert structure["display"] == "none"
    assert structure["active"] is None


def test_every_point_carries_the_status_the_page_renders(client, db_session):
    username = paid_learner(client, db_session, "study-status-field")
    point_id = published_structure(db_session, username)
    assert client.put(f"/knowledge-points/{point_id}/progress",
                      json={"username": username, "status": "learning"}).status_code == 200

    listed = client.get("/knowledge-points", params={"course_id": COURSE}).json()
    rows = {point["id"]: point for point in listed["knowledge_points"]}
    assert rows[point_id]["status"] == "learning"
    # Chapters carry the same field so the nav renders one shape for both levels.
    chapter = next(point for point in listed["knowledge_points"] if point["parent_id"] is None)
    assert chapter["status"] in {"not_started", "learning", "mastered", "review_due"}


def test_the_stored_row_records_its_course_and_its_citations(client, db_session, provider):
    username = paid_learner(client, db_session, "study-row-shape")
    point_id = published_structure(db_session, username)
    client.post(study_content_url(point_id))

    db_session.rollback()
    row = (db_session.query(KnowledgePointStudyContent)
           .filter(KnowledgePointStudyContent.username == username).one())
    assert row.course_id == COURSE
    assert json.loads(row.citations_json or "[]") == []
