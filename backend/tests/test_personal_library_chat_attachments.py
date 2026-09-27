"""P3.1 material scopes: uploads use the shared ingestion path and keep NULL scope fields."""
from __future__ import annotations

import dataclasses

import pytest
from ai.providers import FakeProvider
from conftest import grant_unified_tier, register_and_login
from models import ChatMessage, ChatMessageAttachment, StudyMaterial, User

COURSE = "数据结构"


def _declare_course(client):
    response = client.post("/course-learning/onboarding", json={"major": "计算机科学与技术", "grade": "大二", "semester": "", "selected_courses": [COURSE], "recommended_courses": [], "material_types": [], "course_goals": {}, "onboarding_completed": True})
    assert response.status_code == 200, response.text


@pytest.fixture
def provider(monkeypatch):
    calls = []

    class RecordingProvider(FakeProvider):
        def complete(self, spec):
            calls.append(spec)
            return dataclasses.replace(super().complete(spec), content="已收到")

        def stream(self, spec):
            calls.append(spec)
            return super().stream(spec)

    monkeypatch.setattr("ai.orchestrator.default_provider_factory", lambda name: RecordingProvider(provider=name))
    return calls


def test_personal_and_chat_uploads_create_null_scoped_materials(client, db_session):
    register_and_login(client, "p3-attachments")
    personal = client.post(
        "/personal-materials/upload",
        files={"file": ("notes.txt", b"PERSONAL_UNIQUE_TOKEN_314159", "text/plain")},
    )
    assert personal.status_code == 200, personal.text
    local = client.post(
        "/chat/attachments/upload",
        files={"file": ("local.txt", b"LOCAL_UNIQUE_TOKEN_271828", "text/plain")},
    )
    assert local.status_code == 200, local.text

    personal_row = db_session.get(StudyMaterial, personal.json()["id"])
    local_row = db_session.get(StudyMaterial, local.json()["material_id"])
    assert (personal_row.scope_type, personal_row.course_id, personal_row.subject_key, personal_row.subject) == ("personal", None, None, None)
    assert (local_row.scope_type, local_row.course_id, local_row.subject_key, local_row.subject) == ("chat", None, None, None)
    assert personal_row.chunk_count and local_row.chunk_count

    # One library holds both: scope records which door a file came through, and the label says
    # so in the learner's words, but neither one hides the learner's own file from them.
    listed = {item["id"]: item for item in client.get("/library/materials").json()["materials"]}
    assert personal_row.id in listed and local_row.id in listed
    assert listed[personal_row.id]["scope_type"] == "personal"
    assert listed[personal_row.id]["source_label"] == "个人资料"
    assert listed[local_row.id]["scope_type"] == "chat"
    assert listed[local_row.id]["source_label"] == "聊天上传"


def test_chat_and_stream_accept_uploaded_personal_and_local_attachments(client, db_session, provider):
    register_and_login(client, "p3-attachment-chat")
    user = db_session.query(User).filter_by(username="p3-attachment-chat").one()
    grant_unified_tier(db_session, user.username, "advanced")
    personal = client.post("/personal-materials/upload", files={"file": ("personal.txt", b"PERSONAL_UNIQUE_TOKEN_314159", "text/plain")})
    local = client.post("/chat/attachments/upload", files={"file": ("local.txt", b"LOCAL_UNIQUE_TOKEN_271828", "text/plain")})
    assert personal.status_code == local.status_code == 200
    attachment_ids = [personal.json()["id"], local.json()["material_id"], personal.json()["id"]]
    body = {"message": "请引用附件", "service_key": "course_learning", "attachment_ids": attachment_ids}
    reply = client.post("/chat", json=body)
    assert reply.status_code == 200, reply.text
    message = db_session.query(ChatMessage).filter_by(user_id=user.id, role="user").order_by(ChatMessage.id.desc()).first()
    links = db_session.query(ChatMessageAttachment).filter_by(message_id=message.id).all()
    assert {(link.material_id, link.source_kind) for link in links} == {(attachment_ids[0], "personal"), (attachment_ids[1], "local")}

    streamed = client.post("/chat/stream", json={**body, "session_id": reply.json()["session"]["id"]})
    assert streamed.status_code == 200, streamed.text


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_course_personal_and_local_tokens_reach_real_provider_input(client, db_session, provider, path):
    register_and_login(client, f"p3-context-{path.rsplit('/', 1)[-1]}")
    user = db_session.query(User).filter_by(username=f"p3-context-{path.rsplit('/', 1)[-1]}").one()
    grant_unified_tier(db_session, user.username, "advanced")
    _declare_course(client)
    course = client.post("/materials/upload", data={"username": user.username, "course_id": "data_structure", "subject_key": "data_structure", "subject": COURSE, "track": "course_learning", "source_type": "user_upload"}, files={"file": ("course.txt", b"COURSE_UNIQUE_TOKEN_161803", "text/plain")})
    assert course.status_code == 200, course.text
    personal = client.post("/personal-materials/upload", files={"file": ("personal-token.txt", b"PERSONAL_UNIQUE_TOKEN_314159", "text/plain")})
    local = client.post("/chat/attachments/upload", files={"file": ("local-token.txt", b"LOCAL_UNIQUE_TOKEN_271828", "text/plain")})
    assert personal.status_code == local.status_code == 200
    response = client.post(path, json={"message": "请综合三个资料", "service_key": "course_learning", "course": "data_structure", "course_id": "data_structure", "material_ids": [course.json()["material_id"]], "attachment_ids": [personal.json()["id"], local.json()["material_id"]]})
    assert response.status_code == 200, response.text
    context = "\n".join(str(message.content) for spec in provider for message in spec.messages)
    assert "COURSE_UNIQUE_TOKEN_161803" in context
    assert "PERSONAL_UNIQUE_TOKEN_314159" in context
    assert "LOCAL_UNIQUE_TOKEN_271828" in context
