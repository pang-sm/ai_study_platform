"""One library per learner: every door in, one list out — and explicit reuse that stays explicit.

The product rule these cases pin down: a file the learner uploaded is THEIRS, whichever entry
point put it there, and they may choose it again for any question. `scope_type` still records
where the file came from and what it joins AUTOMATICALLY, which is why the two halves are
asserted together — that the library shows all three scopes, AND that letting a course upload
travel to another course's conversation does not widen what is retrieved without being asked.
"""
from __future__ import annotations

import dataclasses
import uuid

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from fastapi.testclient import TestClient

import main
from models import StudyMaterial
from rag import soft_delete_material_chunks

COURSE_A = "数据结构"
COURSE_B = "操作系统"
LIBRARY = "/library/materials"
ATTACH_REJECT_DETAIL = "附件不存在或不可用"

COURSE_TOKEN = "COURSE_SCOPE_TOKEN_271828"
PERSONAL_TOKEN = "PERSONAL_SCOPE_TOKEN_314159"
CHAT_TOKEN = "CHAT_SCOPE_TOKEN_161803"


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
    """A learner with TWO courses, so "reuse in another course" is a thing they can do."""
    username = f"library-{uuid.uuid4().hex[:8]}"
    register_and_login(client, username)
    grant_unified_tier(db_session, username, "advanced")
    response = client.post("/course-learning/onboarding", json={
        "major": "计算机科学与技术", "grade": "大二", "semester": "上学期",
        "selected_courses": [COURSE_A, COURSE_B], "material_types": ["课件"],
        "onboarding_completed": True,
    })
    assert response.status_code == 200, response.text
    return client, username


def _course_upload(client: TestClient, course: str, filename: str, token: str) -> int:
    response = client.post(f"/course-learning/courses/{course}/materials",
                           files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["material_id"]


def _personal_upload(client: TestClient, filename: str, token: str) -> int:
    response = client.post("/personal-materials/upload", files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _chat_upload(client: TestClient, filename: str, token: str) -> int:
    response = client.post("/chat/attachments/upload", files={"file": (filename, token.encode(), "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["material_id"]


def _library(client: TestClient, q: str = "") -> dict[int, dict]:
    response = client.get(LIBRARY, params={"q": q} if q else None)
    assert response.status_code == 200, response.text
    return {item["id"]: item for item in response.json()["materials"]}


def _context(calls) -> str:
    return "\n".join(str(message.content) for spec in calls for message in spec.messages)


def _ask(client: TestClient, calls, **body):
    response = client.post("/chat", json={"message": "这道题怎么理解", "service_key": "course_learning", **body})
    assert response.status_code == 200, response.text
    return _context(calls)


# ---------------------------------------------------------------- one library, three doors

def test_a_course_upload_appears_in_the_library(learner):
    """The bug this whole change exists for: a course file used to be invisible in the library."""
    client, _ = learner
    material_id = _course_upload(client, COURSE_A, "01_绪论.txt", COURSE_TOKEN)

    row = _library(client)[material_id]
    assert row["filename"] == "01_绪论.txt"
    assert row["scope_type"] == "course"
    assert row["course_id"] == COURSE_A
    # Labelled with the course's own name, never with the word "course".
    assert row["source_label"] == COURSE_A


def test_a_personal_upload_appears_in_the_library(learner):
    client, _ = learner
    material_id = _personal_upload(client, "我的笔记.txt", PERSONAL_TOKEN)

    row = _library(client)[material_id]
    assert row["scope_type"] == "personal"
    assert row["source_label"] == "个人资料"
    assert row["course_id"] == ""


def test_a_chat_upload_appears_in_the_library(learner):
    """A chat upload is still the learner's asset after the conversation that made it."""
    client, _ = learner
    material_id = _chat_upload(client, "聊天里的文件.txt", CHAT_TOKEN)

    row = _library(client)[material_id]
    assert row["scope_type"] == "chat"
    assert row["source_label"] == "聊天上传"


def test_the_library_holds_all_three_scopes_at_once(learner):
    client, _ = learner
    ids = {
        _course_upload(client, COURSE_A, "课件.txt", COURSE_TOKEN),
        _personal_upload(client, "笔记.txt", PERSONAL_TOKEN),
        _chat_upload(client, "附件.txt", CHAT_TOKEN),
    }

    assert set(_library(client)) >= ids
    assert {row["scope_type"] for material_id, row in _library(client).items() if material_id in ids} == {
        "course", "personal", "chat",
    }


def test_the_library_does_not_borrow_another_pattern_of_fields(learner):
    """What a picker needs, and nothing that is the platform's own plumbing."""
    client, _ = learner
    material_id = _course_upload(client, COURSE_A, "课件.txt", COURSE_TOKEN)
    row = _library(client)[material_id]

    assert {"id", "filename", "file_type", "size", "parse_status", "created_at", "scope_type"} <= set(row)
    for forbidden in ("storage_path", "file_path", "chunk_count", "extracted_text", "chunk_text"):
        assert forbidden not in row


# ---------------------------------------------------------------- only your own, only alive

def test_another_learner_sees_none_of_it(learner, db_session):
    client, _ = learner
    ids = {
        _course_upload(client, COURSE_A, "私有课件.txt", COURSE_TOKEN),
        _personal_upload(client, "私有笔记.txt", PERSONAL_TOKEN),
        _chat_upload(client, "私有附件.txt", CHAT_TOKEN),
    }

    with TestClient(main.app) as other:
        register_and_login(other, f"library-other-{uuid.uuid4().hex[:8]}")
        assert set(_library(other)).isdisjoint(ids)


def test_a_deleted_file_leaves_the_library(learner, db_session):
    client, _ = learner
    course_id = _course_upload(client, COURSE_A, "会被删除.txt", COURSE_TOKEN)
    personal_id = _personal_upload(client, "也会删除.txt", PERSONAL_TOKEN)

    assert client.delete(f"/materials/{course_id}").status_code == 200
    assert client.delete(f"/personal-materials/{personal_id}").status_code == 200

    remaining = _library(client)
    assert course_id not in remaining and personal_id not in remaining
    # And the teacher-facing course view agrees, because it is the same row.
    course_list = client.get(f"/course-learning/courses/{COURSE_A}/materials").json()["items"]
    assert all(item["id"] != course_id for item in course_list)


def test_a_deleted_chat_upload_leaves_the_library(learner, db_session):
    client, username = learner
    material_id = _chat_upload(client, "删掉附件.txt", CHAT_TOKEN)
    row = db_session.get(StudyMaterial, material_id)
    row.is_deleted = True
    db_session.commit()
    soft_delete_material_chunks(db_session, material_id)

    assert material_id not in _library(client)


# ---------------------------------------------------------------- explicit reuse

def test_a_course_material_can_be_attached_explicitly(learner, provider):
    """Its owner chose it, so ownership — not scope — decides. The old rule refused this."""
    client, _ = learner
    material_id = _course_upload(client, COURSE_A, "课件.txt", COURSE_TOKEN)

    context = _ask(client, provider, course_id=COURSE_A, attachment_ids=[material_id])
    assert COURSE_TOKEN in context


def test_a_course_material_travels_to_another_course_when_chosen(learner, provider):
    """Uploaded under one course, chosen in another: still the learner's own file."""
    client, _ = learner
    material_id = _course_upload(client, COURSE_A, "数据结构课件.txt", COURSE_TOKEN)

    context = _ask(client, provider, course_id=COURSE_B, attachment_ids=[material_id])
    assert COURSE_TOKEN in context


def test_an_unparsed_or_deleted_file_is_still_refused(learner, db_session):
    client, username = learner
    # Distinct bytes per file: identical content in one domain is refused as a duplicate upload,
    # which is a different rule from the one under test here.
    pending = _personal_upload(client, "还在解析.txt", f"PENDING_{PERSONAL_TOKEN}")
    row = db_session.get(StudyMaterial, pending)
    row.parse_status = "pending"
    db_session.commit()
    assert client.post("/chat", json={
        "message": "x", "service_key": "course_learning", "attachment_ids": [pending],
    }).status_code == 400

    removed = _personal_upload(client, "已经删除.txt", f"REMOVED_{PERSONAL_TOKEN}")
    assert client.delete(f"/personal-materials/{removed}").status_code == 200
    rejected = client.post("/chat", json={
        "message": "x", "service_key": "course_learning", "attachment_ids": [removed],
    })
    assert rejected.status_code == 404 and ATTACH_REJECT_DETAIL in rejected.text


# ---------------------------------------------------------------- automatic retrieval stays scoped

def test_automatic_retrieval_still_refuses_another_course(learner, provider):
    """A file from course A cannot be pulled in as course B's own material — only chosen."""
    client, _ = learner
    other_course_id = _course_upload(client, COURSE_A, "跨课程.txt", COURSE_TOKEN)

    response = client.post("/chat", json={
        "message": "这道题怎么理解", "service_key": "course_learning",
        "course_id": COURSE_B, "material_ids": [other_course_id],
    })
    assert response.status_code == 404


def test_a_file_named_twice_enters_the_prompt_once(learner, provider):
    """Both lists legitimately hold it; the model must still be told about it once."""
    client, _ = learner
    filename = "同一份课件.txt"
    material_id = _course_upload(client, COURSE_A, filename, COURSE_TOKEN)

    context = _ask(
        client, provider,
        course_id=COURSE_A, material_ids=[material_id], attachment_ids=[material_id],
    )

    assert context.count(COURSE_TOKEN) == 1
    named = [line for line in context.splitlines() if line.startswith("【本轮引用资料：")]
    assert len(named) == 1
    assert named[0].count(filename) == 1


def test_two_files_both_named_still_enter_once_each(learner, provider):
    client, _ = learner
    first = _course_upload(client, COURSE_A, "第一份.txt", COURSE_TOKEN)
    second = _personal_upload(client, "第二份.txt", PERSONAL_TOKEN)

    context = _ask(client, provider, course_id=COURSE_A, attachment_ids=[first, second])

    assert context.count(COURSE_TOKEN) == 1
    assert context.count(PERSONAL_TOKEN) == 1
    named = next(line for line in context.splitlines() if line.startswith("【本轮引用资料："))
    assert "第一份.txt" in named and "第二份.txt" in named
