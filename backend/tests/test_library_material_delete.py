"""Deleting from the unified library, and everything that must stop happening afterwards.

One delete covers all three scopes, because the library is one collection of the learner's own
assets: the client never asks which door a file came through. What this pins is the reach of
that single operation — the row leaves the library AND the course view, its preview, download
and re-attachment all stop, its chunks leave course retrieval, and the conversations that
already referenced it keep saying what they said.
"""
from __future__ import annotations

import dataclasses
import uuid

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from fastapi.testclient import TestClient

import main
from models import ChatMessage, StudyMaterial, User

COURSE_A = "数据结构"
LIBRARY = "/library/materials"
COURSE_MATERIALS = f"/course-learning/courses/{COURSE_A}/materials"

COURSE_TOKEN = "COURSE_DELETE_TOKEN_271828"
PERSONAL_TOKEN = "PERSONAL_DELETE_TOKEN_314159"
CHAT_TOKEN = "CHAT_DELETE_TOKEN_161803"


@pytest.fixture
def provider(monkeypatch):
    calls = []

    class Recording(FakeProvider):
        def complete(self, spec):
            calls.append(spec)
            return dataclasses.replace(super().complete(spec), content="已收到")

        def stream(self, spec):
            calls.append(spec)
            return super().stream(spec)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", lambda name: Recording(provider=name))
    return calls


@pytest.fixture
def learner(client, db_session):
    username = f"libdel-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    grant_unified_tier(db_session, username, "advanced")
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE_A], "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    return client, username


def _course_upload(client, filename, token):
    response = client.post(COURSE_MATERIALS, files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["material_id"]


def _personal_upload(client, filename, token):
    response = client.post("/personal-materials/upload", files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _chat_upload(client, filename, token):
    response = client.post("/chat/attachments/upload", files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["material_id"]


def _library(client):
    response = client.get(LIBRARY)
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()["materials"]}


def _delete(client, material_id):
    return client.delete(f"{LIBRARY}/{material_id}")


# ---------------------------------------------------------------- the unified contract

def test_the_library_lists_every_door_the_file_came_through(learner):
    client, _ = learner
    ids = {
        _course_upload(client, "课件.txt", COURSE_TOKEN),
        _personal_upload(client, "笔记.txt", PERSONAL_TOKEN),
        _chat_upload(client, "附件.txt", CHAT_TOKEN),
    }

    listed = _library(client)
    assert ids <= set(listed)
    assert {listed[item]["scope_type"] for item in ids} == {"course", "personal", "chat"}


@pytest.mark.parametrize("scope", ["course", "personal", "chat"])
def test_one_delete_soft_deletes_whichever_scope_it_is(learner, db_session, scope):
    client, username = learner
    if scope == "course":
        material_id = _course_upload(client, "课程课件.txt", f"{COURSE_TOKEN}_{scope}")
    elif scope == "personal":
        material_id = _personal_upload(client, "个人笔记.txt", f"{PERSONAL_TOKEN}_{scope}")
    else:
        material_id = _chat_upload(client, "聊天附件.txt", f"{CHAT_TOKEN}_{scope}")

    response = _delete(client, material_id)
    assert response.status_code == 200, response.text
    assert response.json()["deleted"] is True

    assert material_id not in _library(client)
    row = db_session.get(StudyMaterial, material_id)
    db_session.refresh(row)
    # Soft: the row is still there with its own metadata, and the learner just cannot use it.
    assert row.is_deleted is True and row.deleted_at is not None
    assert row.original_filename


def test_a_course_delete_also_leaves_the_course_view(learner):
    client, _ = learner
    material_id = _course_upload(client, "课程课件.txt", COURSE_TOKEN)

    assert _delete(client, material_id).status_code == 200

    items = client.get(COURSE_MATERIALS).json()["items"]
    assert all(item["id"] != material_id for item in items)


# ---------------------------------------------------------------- only your own

def test_another_learner_cannot_delete_it_or_learn_that_it_exists(learner):
    client, _ = learner
    material_id = _course_upload(client, "私有课件.txt", COURSE_TOKEN)

    with TestClient(main.app) as other:
        register_and_login(other, f"libdel-other-{uuid.uuid4().hex[:8]}")
        response = other.delete(f"{LIBRARY}/{material_id}")
        assert response.status_code == 404, response.text
        # The refusal names nothing: not the file, not its scope, not that it is there at all.
        assert "私有课件" not in response.text
        assert "scope" not in response.text.lower()

    # And the owner's file is untouched by the attempt.
    assert material_id in _library(client)


def test_deleting_twice_is_refused_the_same_way_a_foreign_id_is(learner):
    client, _ = learner
    material_id = _personal_upload(client, "笔记.txt", PERSONAL_TOKEN)

    assert _delete(client, material_id).status_code == 200
    assert _delete(client, material_id).status_code == 404


# ---------------------------------------------------------------- what a delete ends

def test_a_deleted_file_can_no_longer_be_previewed_or_downloaded(learner):
    client, _ = learner
    for material_id in (
        _course_upload(client, "课程课件.txt", COURSE_TOKEN),
        _personal_upload(client, "个人笔记.txt", PERSONAL_TOKEN),
        _chat_upload(client, "聊天附件.txt", CHAT_TOKEN),
    ):
        assert _delete(client, material_id).status_code == 200
        assert client.get(f"/materials/{material_id}/preview").status_code == 404
        assert client.get(f"/materials/{material_id}/download").status_code == 404


def test_a_deleted_file_can_no_longer_be_attached(learner, db_session):
    client, _ = learner
    material_id = _personal_upload(client, "个人笔记.txt", PERSONAL_TOKEN)
    assert _delete(client, material_id).status_code == 200

    response = client.post("/chat", json={
        "message": "还能用它吗", "service_key": "course_learning", "attachment_ids": [material_id],
    })
    assert response.status_code in {400, 404}, response.text


def test_a_deleted_course_material_leaves_course_retrieval(learner):
    """Automatic RAG must stop serving a file the learner removed, not just hide the row."""
    client, _ = learner
    material_id = _course_upload(client, "课程课件.txt", COURSE_TOKEN)

    def search():
        response = client.get("/materials/search", params={
            "q": COURSE_TOKEN, "course_id": COURSE_A, "subject_key": COURSE_A,
        })
        assert response.status_code == 200, response.text
        return response.json()["chunks"]

    assert any(chunk["material_id"] == material_id for chunk in search())

    assert _delete(client, material_id).status_code == 200

    assert all(chunk["material_id"] != material_id for chunk in search())


# ---------------------------------------------------------------- history keeps its record

def test_a_conversation_that_used_the_file_still_says_so(learner, db_session, provider):
    """Deleting an asset ends its future use, not the record of what was already asked with it."""
    client, username = learner
    material_id = _course_upload(client, "课程课件.txt", COURSE_TOKEN)

    sent = client.post("/chat", json={
        "message": "这份课件讲了什么", "service_key": "course_learning",
        "course_id": COURSE_A, "attachment_ids": [material_id],
    })
    assert sent.status_code == 200, sent.text
    session_id = sent.json()["session"]["id"]

    assert _delete(client, material_id).status_code == 200

    detail = client.get(f"/chat/sessions/{session_id}", params={"course": COURSE_A}).json()
    user_message = next(message for message in detail["messages"] if message["role"] == "user")
    attachment = next(item for item in user_message["attachments"] if item["material_id"] == material_id)
    assert attachment["filename"] == "课程课件.txt"
    assert attachment["source_kind"] == "course"
    assert attachment["parse_status"] == "deleted"

    # The relation itself is untouched, which is what keeps the history readable.
    user = db_session.query(User).filter_by(username=username).one()
    message = db_session.query(ChatMessage).filter_by(user_id=user.id, role="user").order_by(ChatMessage.id.desc()).first()
    assert message is not None
